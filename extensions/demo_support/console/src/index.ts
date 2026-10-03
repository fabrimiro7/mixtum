import { ConsolePluginContribution } from '@mixtum/console-api';

export const demoSupportConsoleExtension: ConsolePluginContribution = {
  id: 'demo_support',
  routes: [{
    path: 'support-summary',
    loadComponent: () => import('./support-summary.component').then(module => module.SupportSummaryComponent),
  }],
  navigation: [{ label: 'Riepilogo assistenza', path: '/support-summary' }],
};
