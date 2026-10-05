import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { MIXTUM_CONFIG } from '../../core/runtime-config';
import {
  AuthService, SessionCapabilities, WorkspaceSummary,
} from '../../core/services/auth.service';
import { AdministrationComponent } from './administration.component';

describe('AdministrationComponent', () => {
  let capabilities: BehaviorSubject<SessionCapabilities>;
  let workspaces: BehaviorSubject<WorkspaceSummary[]>;
  let selected: BehaviorSubject<number | null>;
  let controller: HttpTestingController;

  beforeEach(() => {
    capabilities = new BehaviorSubject<SessionCapabilities>({
      platform_admin: false, manage_global_branding: false, managed_workspace_ids: [7],
    });
    workspaces = new BehaviorSubject<WorkspaceSummary[]>([
      { id: 7, name: 'Managed', role: 'owner', can_manage: true },
    ]);
    selected = new BehaviorSubject<number | null>(7);
    TestBed.configureTestingModule({
      imports: [AdministrationComponent],
      providers: [
        { provide: MIXTUM_CONFIG, useValue: { apiBaseUrl: 'http://127.0.0.1:8000' } },
        {
          provide: AuthService,
          useValue: {
            capabilities$: capabilities.asObservable(),
            workspaces$: workspaces.asObservable(),
            selectedWorkspaceId$: selected.asObservable(),
            loadSession: vi.fn().mockResolvedValue(undefined),
            selectWorkspace: vi.fn(),
          },
        },
        provideHttpClient(), provideHttpClientTesting(),
      ],
    });
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('renders empty administrative data and reacts immediately to revoked permission', async () => {
    const fixture = TestBed.createComponent(AdministrationComponent);
    fixture.detectChanges();
    controller.expectOne('http://127.0.0.1:8000/api/workspace/workspace-users/').flush([]);
    controller.expectOne('http://127.0.0.1:8000/api/branding/workspace/7/').flush({ colors: {} });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nessun membro assegnato');
    expect(fixture.nativeElement.textContent).toContain('Branding workspace');

    workspaces.next([{ id: 7, name: 'Managed', role: 'member', can_manage: false }]);
    capabilities.next({ platform_admin: false, manage_global_branding: false, managed_workspace_ids: [] });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('non sono più disponibili');
  });

  it('shows a recoverable error when administrative data cannot be loaded', async () => {
    const fixture = TestBed.createComponent(AdministrationComponent);
    fixture.detectChanges();
    controller.expectOne('http://127.0.0.1:8000/api/workspace/workspace-users/').flush(
      {}, { status: 500, statusText: 'Error' },
    );
    controller.expectOne('http://127.0.0.1:8000/api/branding/workspace/7/').flush({ colors: {} });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Impossibile caricare');
    expect(fixture.nativeElement.textContent).toContain('Riprova');
  });
});
