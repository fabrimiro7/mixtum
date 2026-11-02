import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { consolePlugins } from '../../../../instance/plugins';

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
  readonly branding$ = this.auth.branding$;
  readonly capabilities$ = this.auth.capabilities$;
  readonly canManageSelectedWorkspace$ = this.auth.canManageSelectedWorkspace$;
  readonly productNavigation = [
    { label: 'AI Labs', path: '/ai-labs', productId: 'ai_labs', requiresWorkspaceManagement: false },
    ...consolePlugins.flatMap(plugin => plugin.navigation.map(item => ({ ...item, productId: plugin.id }))),
  ];
  logoutError = false;

  isVisible(productId: string, workspaceId: number | null, workspaces: readonly { id: number; visible_products?: string[] }[]): boolean {
    if (workspaceId === null) return false;
    return workspaces.find(workspace => workspace.id === workspaceId)?.visible_products?.includes(productId) ?? true;
  }

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
