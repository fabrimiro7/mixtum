import { Component, ChangeDetectionStrategy } from '@angular/core';

import { RouterOutlet } from '@angular/router';
import { SidebarComponent } from '../components/sidebar/sidebar.component';

@Component({
    selector: 'app-main-layout',
    imports: [
    RouterOutlet,
    SidebarComponent
],
    templateUrl: './main-layout.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./main-layout.component.scss']
})
export class MainLayoutComponent {
  isMobileMenuOpen = false;

  openMobileMenu(): void {
    this.isMobileMenuOpen = true;
  }

  closeMobileMenu(): void {
    this.isMobileMenuOpen = false;
  }
}
