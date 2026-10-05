import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, combineLatest, firstValueFrom, map } from 'rxjs';

import { KEYCLOAK_CLIENT, MIXTUM_CONFIG } from '../runtime-config';

export interface UserProfile {
  id: number;
  username: string | null;
  email: string | null;
}

export interface WorkspaceSummary {
  id: number;
  name: string;
  role: string | null;
  can_manage: boolean;
}

export interface SessionCapabilities {
  platform_admin: boolean;
  manage_global_branding: boolean;
  managed_workspace_ids: number[];
}

interface SessionResponse {
  user: UserProfile;
  workspaces: WorkspaceSummary[];
  capabilities: SessionCapabilities;
}

export interface BrandingSummary {
  logo_compact: string | null;
  colors: Record<string, string>;
  theme?: { primary: string; on_primary: string };
}

export type SessionStatus = 'signed-out' | 'ready' | 'denied' | 'error';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(MIXTUM_CONFIG);
  private readonly keycloak = inject(KEYCLOAK_CLIENT);

  private readonly currentUserSubject = new BehaviorSubject<UserProfile | null>(null);
  private readonly workspacesSubject = new BehaviorSubject<WorkspaceSummary[]>([]);
  private readonly selectedWorkspaceSubject = new BehaviorSubject<number | null>(null);
  private readonly statusSubject = new BehaviorSubject<SessionStatus>('signed-out');
  private readonly brandingSubject = new BehaviorSubject<BrandingSummary | null>(null);
  private readonly capabilitiesSubject = new BehaviorSubject<SessionCapabilities>({
    platform_admin: false,
    manage_global_branding: false,
    managed_workspace_ids: [],
  });
  private brandingRequest = 0;

  readonly currentUser$ = this.currentUserSubject.asObservable();
  readonly workspaces$ = this.workspacesSubject.asObservable();
  readonly selectedWorkspaceId$ = this.selectedWorkspaceSubject.asObservable();
  readonly status$ = this.statusSubject.asObservable();
  readonly branding$ = this.brandingSubject.asObservable();
  readonly capabilities$ = this.capabilitiesSubject.asObservable();
  readonly canManageSelectedWorkspace$ = combineLatest([
    this.workspacesSubject, this.selectedWorkspaceSubject, this.capabilitiesSubject,
  ]).pipe(map(([workspaces, selected, capabilities]) => capabilities.platform_admin || (
    selected !== null && workspaces.some(workspace => workspace.id === selected && workspace.can_manage)
  )));

  isAuthenticated(): boolean {
    return this.keycloak.authenticated === true;
  }

  async login(): Promise<void> {
    await this.keycloak.login({ redirectUri: window.location.origin + '/' });
  }

  async logout(): Promise<void> {
    this.clearSession();
    await this.keycloak.logout({ redirectUri: window.location.origin + '/' });
  }

  async ensureFreshToken(): Promise<string | null> {
    if (!this.isAuthenticated()) {
      return null;
    }
    try {
      await this.keycloak.updateToken(30);
      return this.keycloak.token ?? null;
    } catch {
      this.clearSession();
      return null;
    }
  }

  async loadSession(): Promise<void> {
    if (!this.isAuthenticated()) {
      this.clearSession();
      await this.loadBranding(null);
      return;
    }
    try {
      const session = await firstValueFrom(this.http.get<SessionResponse>(
        `${this.config.apiBaseUrl.replace(/\/$/, '')}/api/workspace/session/`,
      ));
      this.currentUserSubject.next(session.user);
      this.workspacesSubject.next(session.workspaces);
      this.capabilitiesSubject.next(session.capabilities ?? {
        platform_admin: false,
        manage_global_branding: false,
        managed_workspace_ids: [],
      });
      const previous = Number(sessionStorage.getItem('mixtum.workspaceId'));
      this.selectedWorkspaceSubject.next(
        session.workspaces.some(workspace => workspace.id === previous) ? previous : null,
      );
      this.statusSubject.next('ready');
      void this.loadBranding(this.selectedWorkspaceSubject.value);
    } catch (error) {
      this.clearSession();
      const status = error instanceof HttpErrorResponse && [401, 403].includes(error.status) ? 'denied' : 'error';
      this.statusSubject.next(status);
    }
  }

  selectWorkspace(id: number): void {
    if (!this.workspacesSubject.value.some(workspace => workspace.id === id)) {
      throw new Error('Workspace non disponibile');
    }
    this.selectedWorkspaceSubject.next(id);
    sessionStorage.setItem('mixtum.workspaceId', String(id));
    void this.loadBranding(id);
  }

  selectedWorkspaceId(): number | null {
    return this.selectedWorkspaceSubject.value;
  }

  private clearSession(): void {
    this.brandingRequest++;
    this.brandingSubject.next(null);
    this.currentUserSubject.next(null);
    this.workspacesSubject.next([]);
    this.selectedWorkspaceSubject.next(null);
    this.statusSubject.next('signed-out');
    this.capabilitiesSubject.next({
      platform_admin: false,
      manage_global_branding: false,
      managed_workspace_ids: [],
    });
    sessionStorage.removeItem('mixtum.workspaceId');
  }

  private async loadBranding(workspaceId: number | null): Promise<void> {
    const requestId = ++this.brandingRequest;
    const base = this.config.apiBaseUrl.replace(/\/$/, '');
    const path = workspaceId === null
      ? '/api/branding/effective/'
      : `/api/branding/effective/?workspace_id=${workspaceId}`;
    try {
      const branding = await firstValueFrom(this.http.get<BrandingSummary>(`${base}${path}`));
      if (requestId === this.brandingRequest) {
        this.brandingSubject.next(branding);
      }
    } catch {
      if (requestId === this.brandingRequest) {
        this.brandingSubject.next(null);
      }
    }
  }
}
