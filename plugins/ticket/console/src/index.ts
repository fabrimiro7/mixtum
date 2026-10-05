import { ConsolePluginContribution } from '@mixtum/console-api';

export const ticketConsolePlugin: ConsolePluginContribution = {
  id: 'ticket',
  routes: [{
    path: 'tickets',
    loadComponent: () => import('./ticket-page.component').then(module => module.TicketPageComponent),
  }, {
    path: 'tickets/configuration',
    loadComponent: () => import('./ticket-configuration.component').then(module => module.TicketConfigurationComponent),
  }],
  navigation: [
    { label: 'Ticket', path: '/tickets' },
    { label: 'Configura Ticket', path: '/tickets/configuration', requiresWorkspaceManagement: true },
  ],
};
