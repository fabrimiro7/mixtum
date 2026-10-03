import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { AuthService } from '../../../../core/services/auth.service';

@Component({
  selector: 'app-dashboard',
  imports: [AsyncPipe],
  templateUrl: './dashboard.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private readonly auth = inject(AuthService);
  readonly status$ = this.auth.status$;
  readonly workspaces$ = this.auth.workspaces$;
  readonly selectedWorkspaceId$ = this.auth.selectedWorkspaceId$;
  readonly currentUser$ = this.auth.currentUser$;
}
