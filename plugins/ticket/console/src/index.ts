import { ConsolePluginContribution } from '@mixtum/console-api';

export const ticketConsolePlugin: ConsolePluginContribution = {
  id: 'ticket',
  routes: [{
    path: 'tickets',
    loadComponent: () => import('./ticket-page.component').then(module => module.TicketPageComponent),
  }],
  navigation: [{ label: 'Ticket', path: '/tickets' }],
};
