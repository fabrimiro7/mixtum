import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';

interface Item {
  id: number;
  name: string;
}

type Status = 'select-workspace' | 'loading' | 'ready' | 'empty' | 'forbidden' | 'error';

@Component({
  selector: 'mixtum-starter-plugin-page',
  imports: [FormsModule],
  template: `
    <section aria-labelledby="starter-plugin-title">
      <h1 id="starter-plugin-title">Starter plugin</h1>
      @if (status === 'select-workspace') {
        <p>Seleziona un workspace.</p>
      } @else if (status === 'loading') {
        <p>Caricamento…</p>
      } @else if (status === 'forbidden') {
        <p role="alert">Non hai accesso a questo workspace.</p>
      } @else if (status === 'error') {
        <p role="alert">Impossibile caricare gli elementi.</p>
        <button type="button" (click)="reload()">Riprova</button>
      } @else {
        @if (status === 'empty') {
          <p>Nessun elemento.</p>
        } @else {
          <ul>
            @for (item of items; track item.id) {
              <li>{{ item.name }}</li>
            }
          </ul>
        }
        <form (ngSubmit)="create()">
          <label for="starter-plugin-name">Nome</label>
          <input id="starter-plugin-name" name="name" maxlength="255" [(ngModel)]="name" />
          <button type="submit" [disabled]="!name.trim() || saving">Aggiungi</button>
        </form>
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class ItemPageComponent {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = inject(MIXTUM_API_BASE_URL).replace(/\/$/, '');
  private readonly workspaceIds$ = inject(MIXTUM_SELECTED_WORKSPACE_ID);
  private readonly destroyRef = inject(DestroyRef);
  private sequence = 0;
  private workspaceId: number | null = null;

  status: Status = 'select-workspace';
  items: Item[] = [];
  name = '';
  saving = false;

  constructor() {
    this.workspaceIds$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      this.workspaceId = id;
      void this.reload();
    });
  }

  async reload(): Promise<void> {
    const sequence = ++this.sequence;
    if (this.workspaceId === null) {
      this.items = [];
      this.status = 'select-workspace';
      return;
    }
    this.status = 'loading';
    try {
      const items = await firstValueFrom(this.http.get<Item[]>(`${this.apiBaseUrl}/api/starter-plugin/items/`));
      if (sequence === this.sequence) {
        this.items = items;
        this.status = items.length ? 'ready' : 'empty';
      }
    } catch (error) {
      if (sequence === this.sequence) {
        this.items = [];
        this.status = error instanceof HttpErrorResponse && error.status === 403 ? 'forbidden' : 'error';
      }
    }
  }

  async create(): Promise<void> {
    const name = this.name.trim();
    if (!name || this.workspaceId === null || this.saving) {
      return;
    }
    const workspaceId = this.workspaceId;
    this.saving = true;
    try {
      await firstValueFrom(this.http.post(`${this.apiBaseUrl}/api/starter-plugin/items/`, { name }));
      if (workspaceId === this.workspaceId) {
        this.name = '';
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
