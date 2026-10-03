import { InjectionToken } from '@angular/core';
import { Routes } from '@angular/router';
import { Observable } from 'rxjs';

/** Stable imports for Console plugins; no access to Console implementation services. */
export const MIXTUM_API_BASE_URL = new InjectionToken<string>('Mixtum API base URL');
export const MIXTUM_SELECTED_WORKSPACE_ID = new InjectionToken<Observable<number | null>>('Selected workspace');

export interface ConsolePluginContribution {
  id: string;
  routes: Routes;
  navigation: ReadonlyArray<{ label: string; path: string }>;
}
