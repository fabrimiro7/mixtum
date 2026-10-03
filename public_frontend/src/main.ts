import { registerLocaleData } from '@angular/common';
import localeIt from '@angular/common/locales/it';
import { bootstrapApplication } from '@angular/platform-browser';
import Keycloak from 'keycloak-js';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';
import { loadMixtumConfig } from './app/core/runtime-config';

registerLocaleData(localeIt, 'it-IT');

async function start(): Promise<void> {
  const config = await loadMixtumConfig();
  const keycloak = new Keycloak({ url: config.keycloakUrl, realm: config.realm, clientId: config.clientId });
  await keycloak.init({
    onLoad: 'check-sso',
    flow: 'standard',
    pkceMethod: 'S256',
    checkLoginIframe: false,
    redirectUri: window.location.origin + '/',
  });
  await bootstrapApplication(AppComponent, appConfig(config, keycloak));
}

start().catch((error) => {
  console.error('Mixtum Public Frontend could not start', error);
  document.body.textContent = 'Il portale non è disponibile. Controlla la configurazione e riprova.';
});
