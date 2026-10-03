import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import Keycloak from 'keycloak-js';

import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { KEYCLOAK_CLIENT, MIXTUM_CONFIG, MixtumConfig } from './core/runtime-config';
import { AuthService } from './core/services/auth.service';

export function appConfig(config: MixtumConfig, keycloak: Keycloak): ApplicationConfig {
  return {
    providers: [
      { provide: MIXTUM_CONFIG, useValue: config },
      { provide: KEYCLOAK_CLIENT, useValue: keycloak },
      provideZoneChangeDetection({ eventCoalescing: true }),
      provideHttpClient(withInterceptors([authInterceptor])),
      provideRouter(routes),
      provideAppInitializer(() => inject(AuthService).loadSession()),
    ],
  };
}
