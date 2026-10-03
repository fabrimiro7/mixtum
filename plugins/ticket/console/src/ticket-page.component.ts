import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';

interface Company { id: number; name: string; }
interface TicketItem { id: number; company: number; company_name: string; title: string; description: string; status: string; created_at: string; }
interface TicketPage { results: TicketItem[]; count: number; next: string | null; previous: string | null; }
type ViewStatus = 'select-workspace' | 'loading' | 'ready' | 'empty' | 'forbidden' | 'error';

@Component({
  selector: 'mixtum-ticket-page',
  imports: [FormsModule],
  template: `
    <section aria-labelledby="tickets-title" class="max-w-3xl">
      <h1 id="tickets-title" class="text-2xl font-semibold text-slate-900">Ticket</h1>
      @if (status === 'select-workspace') {
        <p class="mt-6">Seleziona un workspace per vedere i ticket.</p>
      } @else if (status === 'loading') {
        <p class="mt-6">Caricamento in corso…</p>
      } @else if (status === 'forbidden') {
        <p role="alert" class="mt-6 text-amber-800">Non hai accesso ai ticket di questo workspace.</p>
      } @else if (status === 'error') {
        <p role="alert" class="mt-6 text-red-700">Impossibile caricare i ticket.</p>
        <button type="button" class="mt-3 text-indigo-700" (click)="reload()">Riprova</button>
      } @else {
        @if (status === 'empty') {
          <p class="mt-6">Nessun ticket visibile.</p>
        } @else {
          <ul class="mt-6 divide-y divide-slate-200" aria-label="Ticket visibili">
            @for (item of items; track item.id) {
              <li class="py-3">
                <button type="button" class="text-indigo-700 underline" (click)="open(item.id)">{{ item.title }}</button>
                <span class="ml-3 text-slate-600">{{ item.company_name }} · {{ item.status }}</span>
              </li>
            }
          </ul>
          @if (nextPage) {
            <button type="button" class="mt-3 text-indigo-700" (click)="more()">Mostra altri</button>
          }
        }
        @if (selected) {
          <article class="mt-8 rounded border border-slate-200 p-4" aria-label="Dettaglio ticket">
            <h2 class="text-lg font-semibold">{{ selected.title }}</h2>
            <p class="mt-2">{{ selected.company_name }} · {{ selected.status }}</p>
            <p class="mt-3 whitespace-pre-wrap">{{ selected.description }}</p>
          </article>
        }
        @if (companies.length) {
          <form class="mt-8 grid gap-3" (ngSubmit)="create()">
            <h2 class="text-lg font-semibold">Nuova richiesta</h2>
            <label for="ticket-company">Azienda</label>
            <select id="ticket-company" name="company" required [(ngModel)]="companyId" class="rounded border px-3 py-2">
              @for (company of companies; track company.id) {
                <option [ngValue]="company.id">{{ company.name }}</option>
              }
            </select>
            <label for="ticket-title">Titolo</label>
            <input id="ticket-title" name="title" required maxlength="255" [(ngModel)]="title" class="rounded border px-3 py-2" />
            <label for="ticket-description">Descrizione</label>
            <textarea id="ticket-description" name="description" required [(ngModel)]="description" class="rounded border px-3 py-2"></textarea>
            @if (saveError) { <p role="alert" class="text-red-700">Impossibile creare la richiesta.</p> }
            <button type="submit" [disabled]="saving || !companyId || !title.trim() || !description.trim()"
              class="justify-self-start rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50">Crea ticket</button>
          </form>
        }
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class TicketPageComponent {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = inject(MIXTUM_API_BASE_URL).replace(/\/$/, '');
  private readonly workspaceIds$ = inject(MIXTUM_SELECTED_WORKSPACE_ID);
  private readonly destroyRef = inject(DestroyRef);
  private readonly endpoint = `${this.apiBaseUrl}/api/plugin-ticket/tickets/`;
  private readonly companiesEndpoint = `${this.apiBaseUrl}/api/plugin-ticket/companies/`;
  private requestSequence = 0;
  private workspaceId: number | null = null;

  status: ViewStatus = 'select-workspace';
  items: TicketItem[] = [];
  companies: Company[] = [];
  selected: TicketItem | null = null;
  nextPage: string | null = null;
  companyId: number | null = null;
  title = '';
  description = '';
  saving = false;
  saveError = false;

  constructor() {
    this.workspaceIds$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      this.workspaceId = id;
      this.selected = null;
      this.companies = [];
      this.companyId = null;
      this.title = '';
      this.description = '';
      void this.reload();
    });
  }

  async reload(): Promise<void> {
    const sequence = ++this.requestSequence;
    if (this.workspaceId === null) {
      this.items = [];
      this.nextPage = null;
      this.status = 'select-workspace';
      return;
    }
    this.status = 'loading';
    try {
      const [page, companies] = await Promise.all([
        firstValueFrom(this.http.get<TicketPage>(this.endpoint)),
        firstValueFrom(this.http.get<Company[]>(this.companiesEndpoint)),
      ]);
      if (sequence !== this.requestSequence) return;
      this.items = page.results;
      this.nextPage = page.next;
      this.companies = companies;
      this.companyId = companies[0]?.id ?? null;
      this.status = page.results.length ? 'ready' : 'empty';
    } catch (error) {
      if (sequence !== this.requestSequence) return;
      this.items = [];
      this.companies = [];
      this.selected = null;
      this.status = error instanceof HttpErrorResponse && error.status === 403 ? 'forbidden' : 'error';
    }
  }

  async more(): Promise<void> {
    const next = this.nextPage;
    const sequence = this.requestSequence;
    if (!next || this.workspaceId === null) return;
    this.nextPage = null;
    try {
      // Never send the Console bearer token to a pagination URL outside this plugin endpoint.
      const pageUrl = new URL(next, this.endpoint);
      const allowed = new URL(this.endpoint);
      if (pageUrl.origin !== allowed.origin || pageUrl.pathname !== allowed.pathname) {
        throw new Error('Invalid pagination URL');
      }
      const page = await firstValueFrom(this.http.get<TicketPage>(`${this.endpoint}${pageUrl.search}`));
      if (sequence === this.requestSequence) {
        this.items = [...this.items, ...page.results];
        this.nextPage = page.next;
      }
    } catch {
      if (sequence === this.requestSequence) this.status = 'error';
    }
  }

  async open(id: number): Promise<void> {
    const sequence = this.requestSequence;
    try {
      const ticket = await firstValueFrom(this.http.get<TicketItem>(`${this.endpoint}${id}/`));
      if (sequence === this.requestSequence) this.selected = ticket;
    } catch {
      if (sequence === this.requestSequence) this.status = 'error';
    }
  }

  async create(): Promise<void> {
    const companyId = this.companyId;
    const title = this.title.trim();
    const description = this.description.trim();
    if (!companyId || !title || !description || this.workspaceId === null || this.saving) return;
    const workspaceId = this.workspaceId;
    this.saving = true;
    this.saveError = false;
    try {
      const ticket = await firstValueFrom(this.http.post<TicketItem>(this.endpoint, {
        company_id: companyId, title, description,
      }));
      if (workspaceId === this.workspaceId) {
        this.title = '';
        this.description = '';
        this.selected = ticket;
        await this.reload();
        if (workspaceId === this.workspaceId) this.selected = ticket;
      }
    } catch {
      if (workspaceId === this.workspaceId) this.saveError = true;
    } finally {
      this.saving = false;
    }
  }
}
