import { ConsolePluginContribution } from '@mixtum/console-api';

export const externalProbeConsolePlugin: ConsolePluginContribution = {
  id: 'external_probe',
  routes: [{
    path: 'external-probe',
    loadComponent: () => import('./probe-page.component').then(module => module.ProbePageComponent),
  }],
  navigation: [{ label: 'External probe', path: '/external-probe' }],
};
