import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { AuthService } from '../../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  loginError = false;
  isLoading = false;

  async login(): Promise<void> {
    this.loginError = false;
    this.isLoading = true;
    try {
      await this.auth.login();
    } catch {
      this.loginError = true;
      this.isLoading = false;
    }
  }
}
