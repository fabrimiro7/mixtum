import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, firstValueFrom } from 'rxjs';

import { KEYCLOAK_CLIENT, MIXTUM_CONFIG } from '../runtime-config';

export interface UserProfile {
  id: number;
  username: string | null;
  email: string | null;
}

export interface WorkspaceSummary {
  id: number;
  name: string;
  role: string;
}

interface SessionResponse {
  user: UserProfile;
  workspaces: WorkspaceSummary[];
}

export type SessionStatus = 'signed-out' | 'ready' | 'denied' | 'error';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(MIXTUM_CONFIG);
  private readonly keycloak = inject(KEYCLOAK_CLIENT);

  private readonly currentUserSubject = new BehaviorSubject<UserProfile | null>(null);
  private readonly workspacesSubject = new BehaviorSubject<WorkspaceSummary[]>([]);
  private readonly selectedWorkspaceSubject = new BehaviorSubject<number | null>(null);
  private readonly statusSubject = new BehaviorSubject<SessionStatus>('signed-out');

  readonly currentUser$ = this.currentUserSubject.asObservable();
  readonly workspaces$ = this.workspacesSubject.asObservable();
  readonly selectedWorkspaceId$ = this.selectedWorkspaceSubject.asObservable();
  readonly status$ = this.statusSubject.asObservable();

  isAuthenticated(): boolean {
    return this.keycloak.authenticated === true;
  }

  async login(): Promise<void> {
    await this.keycloak.login({ redirectUri: window.location.origin + '/' });
  }

  async logout(): Promise<void> {
    this.clearSession();
    await this.keycloak.logout({ redirectUri: window.location.origin + '/' });
  }

  async ensureFreshToken(): Promise<string | null> {
    if (!this.isAuthenticated()) {
      return null;
    }
    try {
      await this.keycloak.updateToken(30);
      return this.keycloak.token ?? null;
    } catch {
      this.clearSession();
      return null;
    }
  }

  async loadSession(): Promise<void> {
    if (!this.isAuthenticated()) {
      this.clearSession();
      return;
    }
    try {
      const session = await firstValueFrom(this.http.get<SessionResponse>(
        `${this.config.apiBaseUrl.replace(/\/$/, '')}/api/workspace/session/`,
      ));
      this.currentUserSubject.next(session.user);
      this.workspacesSubject.next(session.workspaces);
      const previous = Number(sessionStorage.getItem('mixtum.public.workspaceId'));
      this.selectedWorkspaceSubject.next(
        session.workspaces.some(workspace => workspace.id === previous) ? previous : null,
      );
      this.statusSubject.next('ready');
    } catch (error) {
      this.currentUserSubject.next(null);
      this.workspacesSubject.next([]);
      this.selectedWorkspaceSubject.next(null);
      this.statusSubject.next(
        error instanceof HttpErrorResponse && [401, 403].includes(error.status) ? 'denied' : 'error',
      );
    }
  }

  selectWorkspace(id: number): void {
    if (!this.workspacesSubject.value.some(workspace => workspace.id === id)) {
      throw new Error('Workspace non disponibile');
    }
    this.selectedWorkspaceSubject.next(id);
    sessionStorage.setItem('mixtum.public.workspaceId', String(id));
  }

  selectedWorkspaceId(): number | null {
    return this.selectedWorkspaceSubject.value;
  }

  private clearSession(): void {
    this.currentUserSubject.next(null);
    this.workspacesSubject.next([]);
    this.selectedWorkspaceSubject.next(null);
    this.statusSubject.next('signed-out');
    sessionStorage.removeItem('mixtum.public.workspaceId');
  }
}
