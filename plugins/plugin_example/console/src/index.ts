import { ConsolePluginContribution } from '@mixtum/console-api';

export const exampleConsolePlugin: ConsolePluginContribution = {
  id: 'plugin_example',
  routes: [
    {
      path: 'examples',
      loadComponent: () => import('./example-page.component').then(module => module.ExamplePageComponent),
    },
  ],
  navigation: [{ label: 'Esempi', path: '/examples' }],
};
