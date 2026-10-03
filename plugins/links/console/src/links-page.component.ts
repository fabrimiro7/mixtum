import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';

interface LinkItem {
  id: number;
  title: string;
  url: string;
  label: string;
}

type ViewStatus = 'select-workspace' | 'loading' | 'ready' | 'empty' | 'forbidden' | 'error';

@Component({
  selector: 'mixtum-links-page',
  imports: [FormsModule],
  template: `
    <section aria-labelledby="links-title" class="max-w-3xl">
      <h1 id="links-title" class="text-2xl font-semibold text-slate-900">Link</h1>
      @if (status === 'select-workspace') {
        <p class="mt-6 text-slate-700">Seleziona un workspace per vedere i link.</p>
      } @else if (status === 'loading') {
        <p class="mt-6 text-slate-700">Caricamento in corso…</p>
      } @else if (status === 'forbidden') {
        <p role="alert" class="mt-6 text-amber-800">Non hai accesso ai link di questo workspace.</p>
      } @else if (status === 'error') {
        <p role="alert" class="mt-6 text-red-700">Impossibile caricare o creare il link.</p>
        <button type="button" class="mt-3 text-indigo-700" (click)="reload()">Riprova</button>
      } @else {
        @if (status === 'empty') {
          <p class="mt-6 text-slate-700">Nessun link in questo workspace.</p>
        } @else {
          <ul class="mt-6 divide-y divide-slate-200" aria-label="Link del workspace">
            @for (item of items; track item.id) {
              <li class="py-3">
                <a class="text-indigo-700 underline" [href]="item.url" target="_blank" rel="noopener noreferrer">
                  {{ item.title }}
                </a>
              </li>
            }
          </ul>
        }
        <form class="mt-8 grid gap-3" (ngSubmit)="create()">
          <label for="link-title">Titolo</label>
          <input id="link-title" name="title" type="text" maxlength="255" required [(ngModel)]="title"
            class="rounded-md border border-slate-300 px-3 py-2" />
          <label for="link-url">URL</label>
          <input id="link-url" name="url" type="url" maxlength="1000" required [(ngModel)]="url"
            class="rounded-md border border-slate-300 px-3 py-2" placeholder="https://" />
          <button type="submit" [disabled]="!title.trim() || !url.trim() || saving"
            class="justify-self-start rounded-md bg-indigo-600 px-4 py-2 text-white disabled:opacity-50">
            Aggiungi link
          </button>
        </form>
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class LinksPageComponent {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = inject(MIXTUM_API_BASE_URL).replace(/\/$/, '');
  private readonly workspaceIds$ = inject(MIXTUM_SELECTED_WORKSPACE_ID);
  private readonly destroyRef = inject(DestroyRef);
  private requestSequence = 0;
  private workspaceId: number | null = null;
  private readonly endpoint = `${this.apiBaseUrl}/api/plugin-links/links/`;

  status: ViewStatus = 'select-workspace';
  items: LinkItem[] = [];
  title = '';
  url = '';
  saving = false;

  constructor() {
    this.workspaceIds$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      this.workspaceId = id;
      this.title = '';
      this.url = '';
      void this.reload();
    });
  }

  async reload(): Promise<void> {
    const sequence = ++this.requestSequence;
    if (this.workspaceId === null) {
      this.items = [];
      this.status = 'select-workspace';
      return;
    }
    this.status = 'loading';
    try {
      const items = await firstValueFrom(this.http.get<LinkItem[]>(this.endpoint));
      if (sequence === this.requestSequence) {
        this.items = items;
        this.status = items.length ? 'ready' : 'empty';
      }
    } catch (error) {
      if (sequence === this.requestSequence) {
        this.items = [];
        this.status = error instanceof HttpErrorResponse && error.status === 403 ? 'forbidden' : 'error';
      }
    }
  }

  async create(): Promise<void> {
    const title = this.title.trim();
    const url = this.url.trim();
    if (!title || !url || this.workspaceId === null || this.saving) {
      return;
    }
    const workspaceId = this.workspaceId;
    this.saving = true;
    try {
      await firstValueFrom(this.http.post(this.endpoint, { title, url }));
      if (workspaceId === this.workspaceId) {
        this.title = '';
        this.url = '';
        await this.reload();
      }
    } catch (error) {
      if (workspaceId === this.workspaceId) {
        this.status = error instanceof HttpErrorResponse && error.status === 403 ? 'forbidden' : 'error';
      }
    } finally {
      this.saving = false;
    }
  }
}
