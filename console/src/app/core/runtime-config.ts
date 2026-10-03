import { InjectionToken } from '@angular/core';
import Keycloak from 'keycloak-js';

export interface MixtumConfig {
  apiBaseUrl: string;
  keycloakUrl: string;
  realm: string;
  clientId: string;
}

export const MIXTUM_CONFIG = new InjectionToken<MixtumConfig>('Mixtum runtime config');
export const KEYCLOAK_CLIENT = new InjectionToken<Keycloak>('Keycloak client');

export async function loadMixtumConfig(): Promise<MixtumConfig> {
  const response = await fetch('/assets/mixtum-config.json', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Mixtum runtime configuration is unavailable');
  }
  const config: unknown = await response.json();
  if (!config || typeof config !== 'object') {
    throw new Error('Mixtum runtime configuration is invalid');
  }
  const values = config as Record<string, unknown>;
  for (const field of ['apiBaseUrl', 'keycloakUrl', 'realm', 'clientId']) {
    if (typeof values[field] !== 'string' || !values[field]) {
      throw new Error(`Mixtum runtime configuration is missing ${field}`);
    }
  }
  return values as unknown as MixtumConfig;
}
