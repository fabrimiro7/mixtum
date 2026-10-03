import { ConsolePluginContribution } from '@mixtum/console-api';

export const starterPluginConsolePlugin: ConsolePluginContribution = {
  id: 'starter_plugin',
  routes: [{
    path: 'starter-plugin',
    loadComponent: () => import('./item-page.component').then(module => module.ItemPageComponent),
  }],
  navigation: [{ label: 'Starter plugin', path: '/starter-plugin' }],
};
