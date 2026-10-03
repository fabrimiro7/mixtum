import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';

import { MIXTUM_CONFIG } from '../runtime-config';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const config = inject(MIXTUM_CONFIG);
  const auth = inject(AuthService);
  const apiBase = new URL(config.apiBaseUrl, window.location.origin);
  const target = new URL(request.url, window.location.origin);
  if (target.origin !== apiBase.origin || !target.pathname.startsWith('/api/')) {
    return next(request);
  }

  return from(auth.ensureFreshToken()).pipe(switchMap(token => {
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const workspaceId = auth.selectedWorkspaceId();
    if (workspaceId !== null && target.pathname !== '/api/workspace/session/') {
      headers['X-Workspace-Id'] = String(workspaceId);
    }
    return next(request.clone({ setHeaders: headers }));
  }));
};
