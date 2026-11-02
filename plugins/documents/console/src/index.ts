import { ConsolePluginContribution } from '@mixtum/console-api';

export const documentsConsolePlugin: ConsolePluginContribution = {
  id: 'documents',
  routes: [{
    path: 'documents',
    loadComponent: () => import('./documents-page.component').then(module => module.DocumentsPageComponent),
  }],
  navigation: [{ label: 'Documents', path: '/documents' }],
};
