import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import Keycloak from 'keycloak-js';
import { firstValueFrom } from 'rxjs';

import { KEYCLOAK_CLIENT, MIXTUM_CONFIG, MixtumConfig } from '../runtime-config';
import { authInterceptor } from '../interceptors/auth.interceptor';
import { AuthService } from './auth.service';

describe('AuthService workspace context', () => {
  const config: MixtumConfig = {
    apiBaseUrl: 'http://127.0.0.1:8000',
    keycloakUrl: 'http://127.0.0.1:8080',
    realm: 'mixtum',
    clientId: 'mixtum-console',
  };
  let auth: AuthService;
  let http: HttpClient;
  let controller: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    const keycloak = {
      authenticated: true,
      token: 'test-access-token',
      updateToken: vi.fn().mockResolvedValue(false),
    } as unknown as Keycloak;
    TestBed.configureTestingModule({
      providers: [
        { provide: MIXTUM_CONFIG, useValue: config },
        { provide: KEYCLOAK_CLIENT, useValue: keycloak },
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('does not silently select the only workspace', async () => {
    const loading = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    const request = controller.expectOne('http://127.0.0.1:8000/api/workspace/session/');
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-access-token');
    expect(request.request.headers.has('X-Workspace-Id')).toBe(false);
    request.flush({
      user: { id: 1, username: 'Person', email: 'person@example.test' },
      workspaces: [{ id: 7, name: 'Own', role: 'member' }],
    });
    await loading;
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/').flush({ logo_compact: null, colors: {} });
    expect(auth.selectedWorkspaceId()).toBeNull();
    expect(() => auth.selectWorkspace(8)).toThrow();
    auth.selectWorkspace(7);
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/?workspace_id=7').flush({ logo_compact: null, colors: {} });
    expect(auth.selectedWorkspaceId()).toBe(7);
  });

  it('sends the selected workspace only to the Mixtum API origin', async () => {
    const loading = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/workspace/session/').flush({
      user: { id: 1, username: 'Person', email: 'person@example.test' },
      workspaces: [{ id: 7, name: 'Own', role: 'member' }],
    });
    await loading;
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/').flush({ logo_compact: null, colors: {} });
    auth.selectWorkspace(7);
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/?workspace_id=7').flush({ logo_compact: null, colors: {} });

    const apiRequest = firstValueFrom(http.get('http://127.0.0.1:8000/api/plugin-example/examples/'));
    await new Promise(resolve => setTimeout(resolve, 0));
    const request = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-access-token');
    expect(request.request.headers.get('X-Workspace-Id')).toBe('7');
    request.flush([]);
    await apiRequest;

    const externalRequest = firstValueFrom(http.get('https://external.example.test/data'));
    const external = controller.expectOne('https://external.example.test/data');
    expect(external.request.headers.has('Authorization')).toBe(false);
    external.flush({});
    await externalRequest;
  });

  it('clears stale workspace and branding when a later session request is denied', async () => {
    const initial = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/workspace/session/').flush({
      user: { id: 1, username: 'Person', email: 'person@example.test' },
      workspaces: [{ id: 7, name: 'Own', role: 'member' }],
    });
    await initial;
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/').flush({ logo_compact: null, colors: {} });
    auth.selectWorkspace(7);
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/branding/effective/?workspace_id=7').flush({
      logo_compact: 'previous-logo', colors: {},
    });
    expect(sessionStorage.getItem('mixtum.workspaceId')).toBe('7');

    const denied = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/workspace/session/').flush(
      {}, { status: 403, statusText: 'Forbidden' },
    );
    await denied;

    expect(auth.selectedWorkspaceId()).toBeNull();
    expect(sessionStorage.getItem('mixtum.workspaceId')).toBeNull();
    expect(await firstValueFrom(auth.branding$)).toBeNull();
    expect(await firstValueFrom(auth.status$)).toBe('denied');
  });

  it('loads global branding before an anonymous user opens the login page', async () => {
    TestBed.inject(KEYCLOAK_CLIENT).authenticated = false;
    const loading = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    const request = controller.expectOne('http://127.0.0.1:8000/api/branding/effective/');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({ logo_compact: null, colors: {}, theme: { primary: '#123456', on_primary: '#ffffff' } });
    await loading;
    expect(await firstValueFrom(auth.branding$)).toMatchObject({ theme: { primary: '#123456' } });
    expect(await firstValueFrom(auth.status$)).toBe('signed-out');
  });
});
