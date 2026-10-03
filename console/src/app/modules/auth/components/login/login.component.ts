import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  imports: [AsyncPipe],
  templateUrl: './login.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  readonly branding$ = this.auth.branding$;
  private readonly router = inject(Router);
  isLoading = false;
  error: string | null = null;

  constructor() {
    if (this.auth.isAuthenticated()) {
      queueMicrotask(() => this.router.navigateByUrl('/dashboard'));
    }
  }

  async login(): Promise<void> {
    this.isLoading = true;
    this.error = null;
    try {
      await this.auth.login();
    } catch {
      this.error = 'Impossibile avviare l’accesso. Riprova più tardi.';
      this.isLoading = false;
    }
  }
}
