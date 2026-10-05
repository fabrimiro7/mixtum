import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import Keycloak from 'keycloak-js';

import { routes } from './app.routes';
import { KEYCLOAK_CLIENT, MIXTUM_CONFIG, MixtumConfig } from './core/runtime-config';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { AuthService } from './core/services/auth.service';
import {
  MIXTUM_API_BASE_URL,
  MIXTUM_CAN_MANAGE_SELECTED_WORKSPACE,
  MIXTUM_SELECTED_WORKSPACE_ID,
} from '@mixtum/console-api';

export function appConfig(config: MixtumConfig, keycloak: Keycloak): ApplicationConfig {
  return {
    providers: [
      { provide: MIXTUM_CONFIG, useValue: config },
      { provide: KEYCLOAK_CLIENT, useValue: keycloak },
      { provide: MIXTUM_API_BASE_URL, useValue: config.apiBaseUrl },
      { provide: MIXTUM_SELECTED_WORKSPACE_ID, useFactory: () => inject(AuthService).selectedWorkspaceId$ },
      {
        provide: MIXTUM_CAN_MANAGE_SELECTED_WORKSPACE,
        useFactory: () => inject(AuthService).canManageSelectedWorkspace$,
      },
      provideZoneChangeDetection({ eventCoalescing: true }),
      provideHttpClient(withInterceptors([authInterceptor])),
      provideRouter(routes),
      provideAppInitializer(() => inject(AuthService).loadSession()),
    ],
  };
}
