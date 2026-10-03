import { HttpClient } from '@angular/common/http';
import { AsyncPipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { MIXTUM_API_BASE_URL } from '@mixtum/console-api';

@Component({
  selector: 'mixtum-external-probe-page',
  imports: [AsyncPipe],
  template: '<h1>External probe</h1>@if (status | async; as result) { <p>Workspace {{ result.workspace_id }}</p> }',
})
export class ProbePageComponent {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = inject(MIXTUM_API_BASE_URL);

  readonly status = this.http.get<{ workspace_id: number }>(`${this.apiBaseUrl}/api/external-probe/status/`);
}
