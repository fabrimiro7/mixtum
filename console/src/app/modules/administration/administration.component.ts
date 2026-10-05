import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { combineLatest, firstValueFrom } from 'rxjs';

import { MIXTUM_CONFIG } from '../../core/runtime-config';
import {
  AuthService, SessionCapabilities, UserProfile, WorkspaceSummary,
} from '../../core/services/auth.service';

interface WorkspaceDetail {
  id: number;
  workspace_name: string;
  workspace_description: string | null;
}

interface Membership {
  id: number;
  user: UserProfile;
  workspace: WorkspaceDetail;
  role: 'owner' | 'member';
}

interface Branding {
  colors: Record<string, string>;
}

type PageStatus = 'loading' | 'ready' | 'forbidden' | 'error';

@Component({
  selector: 'app-administration',
  imports: [FormsModule],
  template: `
    <section aria-labelledby="administration-title" class="max-w-4xl">
      <h1 id="administration-title" class="text-2xl font-semibold text-slate-900">Amministrazione</h1>
      @if (status === 'loading') {
        <p class="mt-6">Caricamento in corso…</p>
      } @else if (status === 'forbidden') {
        <p role="alert" class="mt-6 rounded bg-amber-50 p-4 text-amber-900">
          I permessi amministrativi non sono più disponibili per questo workspace.
        </p>
      } @else if (status === 'error') {
        <p role="alert" class="mt-6 text-red-700">Impossibile caricare la configurazione.</p>
        <button type="button" class="mt-3 text-indigo-700" (click)="reload()">Riprova</button>
      } @else {
        @if (capabilities.platform_admin) {
          <form class="mt-8 grid gap-3 rounded border border-slate-200 p-5" (ngSubmit)="createWorkspace()">
            <h2 class="text-lg font-semibold">Nuovo workspace</h2>
            <label for="new-workspace-name">Nome</label>
            <input id="new-workspace-name" name="newWorkspaceName" required maxlength="255"
              [(ngModel)]="newWorkspaceName" class="rounded border px-3 py-2" />
            <label for="new-workspace-owner">Gestore iniziale</label>
            <select id="new-workspace-owner" name="newWorkspaceOwner" required
              [(ngModel)]="newWorkspaceOwnerId" class="rounded border px-3 py-2">
              <option [ngValue]="null">Seleziona un utente verificato</option>
              @for (user of users; track user.id) {
                <option [ngValue]="user.id">{{ user.email || user.username }}</option>
              }
            </select>
            <button type="submit" [disabled]="saving || !newWorkspaceName.trim() || !newWorkspaceOwnerId"
              class="justify-self-start rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50">Crea</button>
          </form>
        }

        @if (selectedWorkspace) {
          <form class="mt-8 grid gap-3 rounded border border-slate-200 p-5" (ngSubmit)="saveWorkspace()">
            <h2 class="text-lg font-semibold">Workspace</h2>
            <label for="workspace-name">Nome</label>
            <input id="workspace-name" name="workspaceName" required maxlength="255"
              [(ngModel)]="workspaceName" class="rounded border px-3 py-2" />
            <label for="workspace-description">Descrizione</label>
            <textarea id="workspace-description" name="workspaceDescription"
              [(ngModel)]="workspaceDescription" class="rounded border px-3 py-2"></textarea>
            <button type="submit" [disabled]="saving || !workspaceName.trim()"
              class="justify-self-start rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50">Salva workspace</button>
          </form>

          <div class="mt-8 rounded border border-slate-200 p-5">
            <h2 class="text-lg font-semibold">Membri</h2>
            @if (members.length === 0) {
              <p class="mt-3 text-slate-600">Nessun membro assegnato.</p>
            } @else {
              <ul class="mt-3 divide-y divide-slate-200">
                @for (membership of members; track membership.id) {
                  <li class="flex flex-wrap items-center gap-3 py-3">
                    <span class="min-w-52 flex-1">{{ membership.user.email || membership.user.username }}</span>
                    <select [attr.aria-label]="'Ruolo di ' + (membership.user.email || membership.user.username)"
                      [ngModel]="membership.role" (ngModelChange)="changeRole(membership, $event)"
                      [ngModelOptions]="{standalone: true}" class="rounded border px-2 py-1">
                      <option value="member">Membro</option>
                      <option value="owner">Gestore</option>
                    </select>
                    <button type="button" class="text-red-700" (click)="removeMember(membership)">Revoca</button>
                  </li>
                }
              </ul>
            }
            @if (capabilities.platform_admin) {
              <form class="mt-4 flex flex-wrap gap-3" (ngSubmit)="addMember()">
                <select name="memberUser" [(ngModel)]="newMemberUserId" class="rounded border px-2 py-1">
                  <option [ngValue]="null">Utente verificato</option>
                  @for (user of users; track user.id) {
                    <option [ngValue]="user.id">{{ user.email || user.username }}</option>
                  }
                </select>
                <select name="memberRole" [(ngModel)]="newMemberRole" class="rounded border px-2 py-1">
                  <option value="member">Membro</option>
                  <option value="owner">Gestore</option>
                </select>
                <button type="submit" [disabled]="saving || !newMemberUserId" class="text-indigo-700">Assegna</button>
              </form>
            }
          </div>

          <form class="mt-8 grid gap-3 rounded border border-slate-200 p-5" (ngSubmit)="saveWorkspaceBranding()">
            <h2 class="text-lg font-semibold">Branding workspace</h2>
            <label for="workspace-primary">Colore principale</label>
            <input id="workspace-primary" name="workspacePrimary" type="color"
              [(ngModel)]="workspacePrimary" class="h-10 w-20 rounded border" />
            <label for="workspace-logo-full">Logo esteso (PNG, JPEG o WebP; massimo 2 MiB)</label>
            <input id="workspace-logo-full" type="file" accept="image/png,image/jpeg,image/webp"
              (change)="selectBrandingFile($event, 'workspace', 'logo_full')" />
            <label for="workspace-logo-compact">Logo compatto</label>
            <input id="workspace-logo-compact" type="file" accept="image/png,image/jpeg,image/webp"
              (change)="selectBrandingFile($event, 'workspace', 'logo_compact')" />
            <label for="workspace-favicon">Favicon (PNG o ICO)</label>
            <input id="workspace-favicon" type="file" accept="image/png,image/x-icon,image/vnd.microsoft.icon"
              (change)="selectBrandingFile($event, 'workspace', 'favicon')" />
            <button type="submit" [disabled]="saving" class="justify-self-start text-indigo-700">Salva branding</button>
          </form>
        } @else {
          <p class="mt-8 rounded bg-slate-50 p-4">Seleziona un workspace per gestirne configurazione e membri.</p>
        }

        @if (capabilities.manage_global_branding) {
          <form class="mt-8 grid gap-3 rounded border border-slate-200 p-5" (ngSubmit)="saveGlobalBranding()">
            <h2 class="text-lg font-semibold">Branding globale</h2>
            <label for="global-primary">Colore principale</label>
            <input id="global-primary" name="globalPrimary" type="color"
              [(ngModel)]="globalPrimary" class="h-10 w-20 rounded border" />
            <label for="global-logo-full">Logo esteso (PNG, JPEG o WebP; massimo 2 MiB)</label>
            <input id="global-logo-full" type="file" accept="image/png,image/jpeg,image/webp"
              (change)="selectBrandingFile($event, 'global', 'logo_full')" />
            <label for="global-logo-compact">Logo compatto</label>
            <input id="global-logo-compact" type="file" accept="image/png,image/jpeg,image/webp"
              (change)="selectBrandingFile($event, 'global', 'logo_compact')" />
            <label for="global-favicon">Favicon (PNG o ICO)</label>
            <input id="global-favicon" type="file" accept="image/png,image/x-icon,image/vnd.microsoft.icon"
              (change)="selectBrandingFile($event, 'global', 'favicon')" />
            <button type="submit" [disabled]="saving" class="justify-self-start text-indigo-700">Salva branding globale</button>
          </form>
        }
        @if (saveError) { <p role="alert" class="mt-4 text-red-700">Operazione non riuscita.</p> }
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class AdministrationComponent {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly base = inject(MIXTUM_CONFIG).apiBaseUrl.replace(/\/$/, '');
  private requestSequence = 0;

  status: PageStatus = 'loading';
  capabilities: SessionCapabilities = {
    platform_admin: false, manage_global_branding: false, managed_workspace_ids: [],
  };
  workspaces: WorkspaceSummary[] = [];
  selectedWorkspace: WorkspaceSummary | null = null;
  members: Membership[] = [];
  users: UserProfile[] = [];
  workspaceName = '';
  workspaceDescription = '';
  workspacePrimary = '#0c0cba';
  globalPrimary = '#0c0cba';
  newWorkspaceName = '';
  newWorkspaceOwnerId: number | null = null;
  newMemberUserId: number | null = null;
  newMemberRole: 'owner' | 'member' = 'member';
  saving = false;
  saveError = false;
  private readonly workspaceBrandingFiles = new Map<string, File>();
  private readonly globalBrandingFiles = new Map<string, File>();

  constructor() {
    combineLatest([
      this.auth.capabilities$, this.auth.workspaces$, this.auth.selectedWorkspaceId$,
    ]).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(([capabilities, workspaces, selectedId]) => {
      this.capabilities = capabilities;
      this.workspaces = workspaces;
      this.selectedWorkspace = workspaces.find(workspace => workspace.id === selectedId) ?? null;
      void this.reload();
    });
  }

  async reload(): Promise<void> {
    const sequence = ++this.requestSequence;
    const canManage = this.capabilities.platform_admin || this.selectedWorkspace?.can_manage === true;
    if (!canManage) {
      this.status = 'forbidden';
      return;
    }
    this.status = 'loading';
    try {
      const membershipsRequest = firstValueFrom(
        this.http.get<Membership[]>(`${this.base}/api/workspace/workspace-users/`),
      );
      const directoryRequest = this.capabilities.platform_admin
        ? firstValueFrom(this.http.get<UserProfile[]>(`${this.base}/api/workspace/users/`))
        : Promise.resolve([] as UserProfile[]);
      const globalBrandingRequest = this.capabilities.platform_admin
        ? firstValueFrom(this.http.get<Branding>(`${this.base}/api/branding/global/`))
        : Promise.resolve(null);
      const workspaceBrandingRequest = this.selectedWorkspace
        ? firstValueFrom(this.http.get<Branding>(
          `${this.base}/api/branding/workspace/${this.selectedWorkspace.id}/`,
        ))
        : Promise.resolve(null);
      const [memberships, directory, globalBranding, workspaceBranding] = await Promise.all([
        membershipsRequest, directoryRequest, globalBrandingRequest, workspaceBrandingRequest,
      ]);
      if (sequence !== this.requestSequence) return;
      const selectedId = this.selectedWorkspace?.id;
      this.members = memberships.filter(item => item.workspace.id === selectedId);
      this.users = directory;
      this.workspaceName = this.selectedWorkspace?.name ?? '';
      this.workspaceDescription = this.members[0]?.workspace.workspace_description ?? '';
      this.workspacePrimary = workspaceBranding?.colors['--ed-blue'] ?? '#0c0cba';
      this.globalPrimary = globalBranding?.colors['--ed-blue'] ?? '#0c0cba';
      this.status = 'ready';
    } catch (error) {
      if (sequence !== this.requestSequence) return;
      this.status = error instanceof HttpErrorResponse && [401, 403, 404].includes(error.status)
        ? 'forbidden' : 'error';
    }
  }

  async createWorkspace(): Promise<void> {
    if (!this.newWorkspaceName.trim() || !this.newWorkspaceOwnerId) return;
    await this.mutate(async () => {
      const created = await firstValueFrom(this.http.post<WorkspaceDetail>(
        `${this.base}/api/workspace/workspaces/`,
        { workspace_name: this.newWorkspaceName.trim(), owner_user_id: this.newWorkspaceOwnerId },
      ));
      this.newWorkspaceName = '';
      this.newWorkspaceOwnerId = null;
      await this.auth.loadSession();
      this.auth.selectWorkspace(created.id);
    });
  }

  async saveWorkspace(): Promise<void> {
    if (!this.selectedWorkspace) return;
    await this.mutate(() => firstValueFrom(this.http.patch(
      `${this.base}/api/workspace/workspaces/${this.selectedWorkspace!.id}/`,
      { workspace_name: this.workspaceName.trim(), workspace_description: this.workspaceDescription },
    )).then(() => this.auth.loadSession()));
  }

  async addMember(): Promise<void> {
    if (!this.selectedWorkspace || !this.newMemberUserId) return;
    await this.mutate(() => firstValueFrom(this.http.post(`${this.base}/api/workspace/workspace-users/`, {
      user_id: this.newMemberUserId, workspace_id: this.selectedWorkspace!.id, role: this.newMemberRole,
    })));
  }

  async changeRole(membership: Membership, role: 'owner' | 'member'): Promise<void> {
    await this.mutate(() => firstValueFrom(this.http.patch(
      `${this.base}/api/workspace/workspace-users/${membership.id}/`, { role },
    )));
  }

  async removeMember(membership: Membership): Promise<void> {
    await this.mutate(() => firstValueFrom(this.http.delete(
      `${this.base}/api/workspace/workspace-users/${membership.id}/`,
    )));
  }

  async saveWorkspaceBranding(): Promise<void> {
    if (!this.selectedWorkspace) return;
    const saved = await this.mutate(() => firstValueFrom(this.http.patch(
      `${this.base}/api/branding/workspace/${this.selectedWorkspace!.id}/`,
      this.brandingPayload(this.workspacePrimary, this.workspaceBrandingFiles),
    )));
    if (saved) this.workspaceBrandingFiles.clear();
  }

  async saveGlobalBranding(): Promise<void> {
    const saved = await this.mutate(() => firstValueFrom(this.http.patch(
      `${this.base}/api/branding/global/`, this.brandingPayload(this.globalPrimary, this.globalBrandingFiles),
    )));
    if (saved) this.globalBrandingFiles.clear();
  }

  selectBrandingFile(
    event: Event, scope: 'workspace' | 'global', field: 'logo_full' | 'logo_compact' | 'favicon',
  ): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    const files = scope === 'workspace' ? this.workspaceBrandingFiles : this.globalBrandingFiles;
    if (file) files.set(field, file);
    else files.delete(field);
  }

  private brandingPayload(color: string, files: Map<string, File>): FormData {
    const payload = new FormData();
    payload.append('colors', JSON.stringify({ '--ed-blue': color }));
    for (const [field, file] of files) payload.append(field, file, file.name);
    return payload;
  }

  private async mutate(operation: () => Promise<unknown>): Promise<boolean> {
    if (this.saving) return false;
    this.saving = true;
    this.saveError = false;
    try {
      await operation();
      await this.reload();
      return true;
    } catch (error) {
      this.saveError = true;
      if (error instanceof HttpErrorResponse && [401, 403, 404].includes(error.status)) {
        this.status = 'forbidden';
        await this.auth.loadSession();
      }
      return false;
    } finally {
      this.saving = false;
    }
  }
}
