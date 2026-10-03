import { Component, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';


@Component({
    selector: 'app-header',
    imports: [],
    templateUrl: './header.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./header.component.scss']
})
export class HeaderComponent {

  @Output() mobileMenuToggled = new EventEmitter<void>();

  isProfileMenuOpen = false;

  toggleMobileMenu(): void {
    console.log('Header: Toggle mobile menu button clicked');
    this.mobileMenuToggled.emit();
  }

  toggleProfileMenu(): void {
    this.isProfileMenuOpen = !this.isProfileMenuOpen;
  }

}