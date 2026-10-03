import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';

interface Summary { open: number; closed: number; }
type ViewStatus = 'select-workspace' | 'loading' | 'ready' | 'forbidden' | 'error';

@Component({
  selector: 'mixtum-demo-support-summary',
  template: `
    <section aria-labelledby="support-summary-title" class="max-w-3xl">
      <h1 id="support-summary-title" class="text-2xl font-semibold">Riepilogo assistenza</h1>
      @if (status === 'select-workspace') {
        <p class="mt-6">Seleziona un workspace.</p>
      } @else if (status === 'loading') {
        <p class="mt-6">Caricamento in corso…</p>
      } @else if (status === 'forbidden') {
        <p role="alert" class="mt-6">Accesso non consentito.</p>
      } @else if (status === 'error') {
        <p role="alert" class="mt-6">Impossibile caricare il riepilogo.</p>
        <button type="button" class="text-indigo-700" (click)="reload()">Riprova</button>
      } @else {
        <p class="mt-6">Ticket aperti: {{ summary?.open }}</p>
        <p>Ticket chiusi: {{ summary?.closed }}</p>
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class SupportSummaryComponent {
  private readonly http = inject(HttpClient);
  private readonly endpoint = `${inject(MIXTUM_API_BASE_URL).replace(/\/$/, '')}/api/demo-support/summary/`;
  private readonly destroyRef = inject(DestroyRef);
  private workspaceId: number | null = null;
  private sequence = 0;
  status: ViewStatus = 'select-workspace';
  summary: Summary | null = null;

  constructor() {
    inject(MIXTUM_SELECTED_WORKSPACE_ID).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      this.workspaceId = id;
      this.summary = null;
      void this.reload();
    });
  }

  async reload(): Promise<void> {
    const sequence = ++this.sequence;
    if (this.workspaceId === null) {
      this.status = 'select-workspace';
      this.summary = null;
      return;
    }
    this.status = 'loading';
    try {
      const summary = await firstValueFrom(this.http.get<Summary>(this.endpoint));
      if (sequence === this.sequence) {
        this.summary = summary;
        this.status = 'ready';
      }
    } catch (error) {
      if (sequence === this.sequence) {
        this.summary = null;
        this.status = error instanceof HttpErrorResponse && error.status === 403 ? 'forbidden' : 'error';
      }
    }
  }
}
