import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import Keycloak from 'keycloak-js';
import { firstValueFrom } from 'rxjs';

import { authInterceptor } from '../interceptors/auth.interceptor';
import { KEYCLOAK_CLIENT, MIXTUM_CONFIG, MixtumConfig } from '../runtime-config';
import { AuthService } from './auth.service';

describe('Public AuthService workspace context', () => {
  const config: MixtumConfig = {
    apiBaseUrl: 'http://127.0.0.1:8000',
    keycloakUrl: 'http://127.0.0.1:8080',
    realm: 'mixtum',
    clientId: 'mixtum-public',
  };
  let auth: AuthService;
  let http: HttpClient;
  let controller: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    const keycloak = {
      authenticated: true,
      token: 'public-access-token',
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

  it('requires explicit selection and ignores an unauthorized saved workspace', async () => {
    sessionStorage.setItem('mixtum.public.workspaceId', '8');
    const loading = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    const request = controller.expectOne('http://127.0.0.1:8000/api/workspace/session/');
    expect(request.request.headers.get('Authorization')).toBe('Bearer public-access-token');
    expect(request.request.headers.has('X-Workspace-Id')).toBe(false);
    request.flush({
      user: { id: 1, username: 'Person', email: 'person@example.test' },
      workspaces: [{ id: 7, name: 'Own', role: 'member' }],
    });
    await loading;
    expect(auth.selectedWorkspaceId()).toBeNull();
    expect(() => auth.selectWorkspace(8)).toThrow();
    auth.selectWorkspace(7);
    expect(auth.selectedWorkspaceId()).toBe(7);
  });

  it('does not send bearer tokens to another origin', async () => {
    const loading = auth.loadSession();
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/workspace/session/').flush({
      user: { id: 1, username: 'Person', email: 'person@example.test' },
      workspaces: [{ id: 7, name: 'Own', role: 'member' }],
    });
    await loading;
    auth.selectWorkspace(7);

    const apiResponse = firstValueFrom(http.get('http://127.0.0.1:8000/api/plugin-example/examples/'));
    await new Promise(resolve => setTimeout(resolve, 0));
    const apiRequest = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    expect(apiRequest.request.headers.get('X-Workspace-Id')).toBe('7');
    apiRequest.flush([]);
    await apiResponse;

    const externalResponse = firstValueFrom(http.get('https://external.example.test/data'));
    const externalRequest = controller.expectOne('https://external.example.test/data');
    expect(externalRequest.request.headers.has('Authorization')).toBe(false);
    externalRequest.flush({});
    await externalResponse;
  });
});
