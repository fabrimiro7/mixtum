import { ConsolePluginContribution } from '@mixtum/console-api';
import { exampleConsolePlugin } from '@mixtum/plugin-example-console';
import { linksConsolePlugin } from '@mixtum/plugin-links-console';
import { ticketConsolePlugin } from '@mixtum/plugin-ticket-console';
import { demoSupportConsoleExtension } from '@mixtum/extension-demo-support-console';
import composition from '../../../mixtum_instance/composition.json';

/** This file belongs to the instance; the shared Console shell remains unchanged. */
const available: readonly ConsolePluginContribution[] = [
  exampleConsolePlugin, linksConsolePlugin, ticketConsolePlugin, demoSupportConsoleExtension,
];
export function selectConsolePlugins(
  enabledIds: readonly string[], contributions: readonly ConsolePluginContribution[],
): readonly ConsolePluginContribution[] {
  const enabled = new Set(enabledIds);
  return contributions.filter(plugin => enabled.has(plugin.id));
}
export const consolePlugins = selectConsolePlugins([...composition.plugins, ...composition.extensions], available);
