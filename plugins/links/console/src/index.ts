import { ConsolePluginContribution } from '@mixtum/console-api';

export const linksConsolePlugin: ConsolePluginContribution = {
  id: 'links',
  routes: [{
    path: 'links',
    loadComponent: () => import('./links-page.component').then(module => module.LinksPageComponent),
  }],
  navigation: [{ label: 'Link', path: '/links' }],
};
