import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-sidebar',
  imports: [AsyncPipe, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent {
  private readonly auth = inject(AuthService);
  readonly currentUser$ = this.auth.currentUser$;
  readonly workspaces$ = this.auth.workspaces$;
  readonly selectedWorkspaceId$ = this.auth.selectedWorkspaceId$;
  logoutError = false;

  selectWorkspace(event: Event): void {
    const id = Number((event.target as HTMLSelectElement).value);
    if (id > 0) {
      this.auth.selectWorkspace(id);
    }
  }

  async logout(): Promise<void> {
    this.logoutError = false;
    try {
      await this.auth.logout();
    } catch {
      this.logoutError = true;
    }
  }
}
