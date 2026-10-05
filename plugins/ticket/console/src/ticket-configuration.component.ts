import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { combineLatest, firstValueFrom } from 'rxjs';

import {
  MIXTUM_API_BASE_URL,
  MIXTUM_CAN_MANAGE_SELECTED_WORKSPACE,
  MIXTUM_SELECTED_WORKSPACE_ID,
} from '@mixtum/console-api';

interface UserSummary { id: number; username: string | null; email: string | null; }
interface CompanyMembership { id: number; user: UserSummary; role: 'requester' | 'referent'; }
interface OperatorGrant { id: number; user: UserSummary; }
interface CompanyConfiguration {
  id: number;
  name: string;
  memberships: CompanyMembership[];
  operator_grants: OperatorGrant[];
}
interface Manager { id: number; user: UserSummary; }
interface Configuration { companies: CompanyConfiguration[]; managers: Manager[]; available_users: UserSummary[]; }
type PageStatus = 'select-workspace' | 'loading' | 'ready' | 'forbidden' | 'error';

@Component({
  selector: 'mixtum-ticket-configuration',
  imports: [FormsModule],
  template: `
    <section aria-labelledby="ticket-configuration-title" class="max-w-4xl">
      <h1 id="ticket-configuration-title" class="text-2xl font-semibold text-slate-900">Configurazione Ticket</h1>
      @if (status === 'select-workspace') {
        <p class="mt-6">Seleziona un workspace.</p>
      } @else if (status === 'loading') {
        <p class="mt-6">Caricamento in corso…</p>
      } @else if (status === 'forbidden') {
        <p role="alert" class="mt-6 rounded bg-amber-50 p-4 text-amber-900">
          Non puoi più configurare Ticket per questo workspace.
        </p>
      } @else if (status === 'error') {
        <p role="alert" class="mt-6 text-red-700">Impossibile caricare la configurazione Ticket.</p>
        <button type="button" class="mt-3 text-indigo-700" (click)="reload()">Riprova</button>
      } @else {
        <form class="mt-8 flex flex-wrap gap-3 rounded border border-slate-200 p-5" (ngSubmit)="createCompany()">
          <label for="ticket-company-name" class="w-full font-semibold">Nuova azienda</label>
          <input id="ticket-company-name" name="companyName" required maxlength="255" [(ngModel)]="companyName"
            class="min-w-64 flex-1 rounded border px-3 py-2" />
          <button type="submit" [disabled]="saving || !companyName.trim()" class="text-indigo-700">Aggiungi</button>
        </form>

        @if (companies.length === 0) {
          <p class="mt-6 rounded bg-slate-50 p-4">Nessuna azienda configurata.</p>
        }
        @for (company of companies; track company.id) {
          <article class="mt-6 rounded border border-slate-200 p-5">
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-lg font-semibold">{{ company.name }}</h2>
              <button type="button" class="text-red-700" (click)="removeCompany(company)">Rimuovi azienda</button>
            </div>
            <h3 class="mt-5 font-semibold">Richiedenti e referenti</h3>
            @if (company.memberships.length === 0) { <p class="mt-2 text-slate-600">Nessuno.</p> }
            <ul class="divide-y divide-slate-200">
              @for (membership of company.memberships; track membership.id) {
                <li class="flex flex-wrap items-center gap-3 py-2">
                  <span class="flex-1">{{ membership.user.email || membership.user.username }}</span>
                  <select [ngModel]="membership.role" (ngModelChange)="changeMembership(membership, $event)"
                    [ngModelOptions]="{standalone: true}" class="rounded border px-2 py-1">
                    <option value="requester">Richiedente</option>
                    <option value="referent">Referente</option>
                  </select>
                  <button type="button" class="text-red-700" (click)="removeMembership(membership)">Revoca</button>
                </li>
              }
            </ul>
            <form class="mt-3 flex flex-wrap gap-2" (ngSubmit)="addMembership(company)">
              <select name="membershipUser{{company.id}}" [(ngModel)]="membershipUserId" class="rounded border px-2 py-1">
                <option [ngValue]="null">Utente assegnato</option>
                @for (user of users; track user.id) { <option [ngValue]="user.id">{{ user.email || user.username }}</option> }
              </select>
              <select name="membershipRole{{company.id}}" [(ngModel)]="membershipRole" class="rounded border px-2 py-1">
                <option value="requester">Richiedente</option>
                <option value="referent">Referente</option>
              </select>
              <button type="submit" [disabled]="saving || !membershipUserId" class="text-indigo-700">Assegna</button>
            </form>

            <h3 class="mt-5 font-semibold">Operatori</h3>
            <ul class="divide-y divide-slate-200">
              @for (grant of company.operator_grants; track grant.id) {
                <li class="flex items-center gap-3 py-2">
                  <span class="flex-1">{{ grant.user.email || grant.user.username }}</span>
                  <button type="button" class="text-red-700" (click)="removeOperator(grant)">Revoca</button>
                </li>
              }
            </ul>
            <form class="mt-3 flex gap-2" (ngSubmit)="addOperator(company)">
              <select name="operatorUser{{company.id}}" [(ngModel)]="operatorUserId" class="rounded border px-2 py-1">
                <option [ngValue]="null">Utente assegnato</option>
                @for (user of users; track user.id) { <option [ngValue]="user.id">{{ user.email || user.username }}</option> }
              </select>
              <button type="submit" [disabled]="saving || !operatorUserId" class="text-indigo-700">Aggiungi operatore</button>
            </form>
          </article>
        }

        <div class="mt-8 rounded border border-slate-200 p-5">
          <h2 class="text-lg font-semibold">Responsabili assistenza</h2>
          <ul class="divide-y divide-slate-200">
            @for (manager of managers; track manager.id) {
              <li class="flex items-center gap-3 py-2">
                <span class="flex-1">{{ manager.user.email || manager.user.username }}</span>
                <button type="button" class="text-red-700" (click)="removeManager(manager)">Revoca</button>
              </li>
            }
          </ul>
          <form class="mt-3 flex gap-2" (ngSubmit)="addManager()">
            <select name="managerUser" [(ngModel)]="managerUserId" class="rounded border px-2 py-1">
              <option [ngValue]="null">Utente assegnato</option>
              @for (user of users; track user.id) { <option [ngValue]="user.id">{{ user.email || user.username }}</option> }
            </select>
            <button type="submit" [disabled]="saving || !managerUserId" class="text-indigo-700">Aggiungi responsabile</button>
          </form>
        </div>
        @if (saveError) { <p role="alert" class="mt-4 text-red-700">Operazione non riuscita.</p> }
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class TicketConfigurationComponent {
  private readonly http = inject(HttpClient);
  private readonly base = inject(MIXTUM_API_BASE_URL).replace(/\/$/, '');
  private readonly workspaceId$ = inject(MIXTUM_SELECTED_WORKSPACE_ID);
  private readonly canManage$ = inject(MIXTUM_CAN_MANAGE_SELECTED_WORKSPACE);
  private readonly destroyRef = inject(DestroyRef);
  private readonly endpoint = `${this.base}/api/plugin-ticket/configuration/`;
  private requestSequence = 0;
  private workspaceId: number | null = null;
  private canManage = false;

  status: PageStatus = 'select-workspace';
  companies: CompanyConfiguration[] = [];
  managers: Manager[] = [];
  users: UserSummary[] = [];
  companyName = '';
  membershipUserId: number | null = null;
  membershipRole: 'requester' | 'referent' = 'requester';
  operatorUserId: number | null = null;
  managerUserId: number | null = null;
  saving = false;
  saveError = false;

  constructor() {
    combineLatest([this.workspaceId$, this.canManage$])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(([workspaceId, canManage]) => {
        this.workspaceId = workspaceId;
        this.canManage = canManage;
        void this.reload();
      });
  }

  async reload(): Promise<void> {
    const sequence = ++this.requestSequence;
    if (this.workspaceId === null) {
      this.status = 'select-workspace';
      this.clear();
      return;
    }
    if (!this.canManage) {
      this.status = 'forbidden';
      this.clear();
      return;
    }
    this.status = 'loading';
    try {
      const configuration = await firstValueFrom(this.http.get<Configuration>(this.endpoint));
      if (sequence !== this.requestSequence) return;
      this.companies = configuration.companies;
      this.managers = configuration.managers;
      this.users = configuration.available_users;
      this.status = 'ready';
    } catch (error) {
      if (sequence !== this.requestSequence) return;
      this.clear();
      this.status = error instanceof HttpErrorResponse && [401, 403, 404].includes(error.status)
        ? 'forbidden' : 'error';
    }
  }

  createCompany(): Promise<void> {
    const name = this.companyName.trim();
    if (!name) return Promise.resolve();
    return this.mutate(() => firstValueFrom(this.http.post(`${this.endpoint}companies/`, { name })))
      .then(() => { this.companyName = ''; });
  }

  removeCompany(company: CompanyConfiguration): Promise<void> {
    return this.mutate(() => firstValueFrom(this.http.delete(`${this.endpoint}companies/${company.id}/`)));
  }

  addMembership(company: CompanyConfiguration): Promise<void> {
    if (!this.membershipUserId) return Promise.resolve();
    return this.mutate(() => firstValueFrom(this.http.post(
      `${this.endpoint}companies/${company.id}/memberships/`,
      { user_id: this.membershipUserId, role: this.membershipRole },
    )));
  }

  changeMembership(membership: CompanyMembership, role: 'requester' | 'referent'): Promise<void> {
    return this.mutate(() => firstValueFrom(this.http.patch(
      `${this.endpoint}memberships/${membership.id}/`, { role },
    )));
  }

  removeMembership(membership: CompanyMembership): Promise<void> {
    return this.mutate(() => firstValueFrom(this.http.delete(`${this.endpoint}memberships/${membership.id}/`)));
  }

  addOperator(company: CompanyConfiguration): Promise<void> {
    if (!this.operatorUserId) return Promise.resolve();
    return this.mutate(() => firstValueFrom(this.http.post(
      `${this.endpoint}companies/${company.id}/operators/`, { user_id: this.operatorUserId },
    )));
  }

  removeOperator(grant: OperatorGrant): Promise<void> {
    return this.mutate(() => firstValueFrom(this.http.delete(`${this.endpoint}operators/${grant.id}/`)));
  }

  addManager(): Promise<void> {
    if (!this.managerUserId) return Promise.resolve();
    return this.mutate(() => firstValueFrom(this.http.post(
      `${this.endpoint}managers/`, { user_id: this.managerUserId },
    )));
  }

  removeManager(manager: Manager): Promise<void> {
    return this.mutate(() => firstValueFrom(this.http.delete(`${this.endpoint}managers/${manager.id}/`)));
  }

  private async mutate(operation: () => Promise<unknown>): Promise<void> {
    if (this.saving || this.workspaceId === null) return;
    const workspaceId = this.workspaceId;
    this.saving = true;
    this.saveError = false;
    try {
      await operation();
      if (workspaceId === this.workspaceId) await this.reload();
    } catch (error) {
      this.saveError = true;
      if (error instanceof HttpErrorResponse && [401, 403, 404].includes(error.status)) {
        this.status = 'forbidden';
        this.clear();
      }
    } finally {
      this.saving = false;
    }
  }

  private clear(): void {
    this.companies = [];
    this.managers = [];
    this.users = [];
  }
}
