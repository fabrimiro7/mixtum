import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';
import { ticketConsolePlugin } from '@mixtum/plugin-ticket-console';
import { consolePlugins, selectConsolePlugins } from '../instance/plugins';

describe('Ticket Console plugin', () => {
  interface TicketPage {
    companyId: number | null;
    title: string;
    description: string;
    create(): Promise<void>;
    open(id: number): Promise<void>;
    more(): Promise<void>;
  }
  const endpoint = 'http://127.0.0.1:8000/api/plugin-ticket/tickets/';
  const companiesEndpoint = 'http://127.0.0.1:8000/api/plugin-ticket/companies/';
  const item = { id: 1, company: 2, company_name: 'Acme', title: 'Errore',
    description: 'Dettaglio', status: 'open', created_at: '2026-10-02T10:00:00Z' };
  let workspaceIds: BehaviorSubject<number | null>;
  let controller: HttpTestingController;

  async function createPage() {
    const component = await (ticketConsolePlugin.routes[0].loadComponent!() as Promise<Type<TicketPage>>);
    return TestBed.createComponent(component);
  }

  beforeEach(() => {
    workspaceIds = new BehaviorSubject<number | null>(null);
    TestBed.configureTestingModule({
      providers: [
        { provide: MIXTUM_API_BASE_URL, useValue: 'http://127.0.0.1:8000' },
        { provide: MIXTUM_SELECTED_WORKSPACE_ID, useValue: workspaceIds.asObservable() },
        provideHttpClient(), provideHttpClientTesting(),
      ],
    });
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('registers via the public contract and disappears when disabled', () => {
    expect(consolePlugins.map(plugin => plugin.id)).toContain('ticket');
    expect(selectConsolePlugins(['links'], [ticketConsolePlugin])).toEqual([]);
    expect(ticketConsolePlugin.routes[0].path).toBe('tickets');
  });

  it('lists, reads detail and creates a request for an authorized company', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Seleziona un workspace');
    workspaceIds.next(7);
    controller.expectOne(endpoint).flush({ results: [item], count: 1, next: null, previous: null });
    controller.expectOne(companiesEndpoint).flush([{ id: 2, name: 'Acme' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Errore');
    expect(fixture.componentInstance.companyId).toBe(2);

    const opening = fixture.componentInstance.open(1);
    controller.expectOne(`${endpoint}1/`).flush(item);
    await opening;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Dettaglio');

    fixture.componentInstance.title = 'Nuovo';
    fixture.componentInstance.description = 'Aiuto';
    const creating = fixture.componentInstance.create();
    const post = controller.expectOne(endpoint);
    expect(post.request.body).toEqual({ company_id: 2, title: 'Nuovo', description: 'Aiuto' });
    post.flush({ ...item, id: 3, title: 'Nuovo' });
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne(endpoint).flush({ results: [{ ...item, id: 3, title: 'Nuovo' }], count: 1, next: null, previous: null });
    controller.expectOne(companiesEndpoint).flush([{ id: 2, name: 'Acme' }]);
    await creating;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nuovo');
  });

  it('discards stale responses when switching workspace', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    const oldPage = controller.expectOne(endpoint);
    const oldCompanies = controller.expectOne(companiesEndpoint);
    workspaceIds.next(8);
    controller.expectOne(endpoint).flush({ results: [{ ...item, company_name: 'Beta', title: 'Nuovo workspace' }], count: 1, next: null, previous: null });
    controller.expectOne(companiesEndpoint).flush([]);
    oldPage.flush({ results: [item], count: 1, next: null, previous: null });
    oldCompanies.flush([{ id: 2, name: 'Acme' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nuovo workspace');
    expect(fixture.nativeElement.textContent).not.toContain('Acme');
  });

  it('shows access denied', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    controller.expectOne(endpoint).flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    controller.expectOne(companiesEndpoint).flush([]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Non hai accesso');
  });

  it('does not follow an off-origin pagination URL with credentials', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    controller.expectOne(endpoint).flush({ results: [item], count: 2,
      next: 'https://attacker.example/tickets/?offset=1', previous: null });
    controller.expectOne(companiesEndpoint).flush([]);
    await new Promise(resolve => setTimeout(resolve, 0));
    await fixture.componentInstance.more();
    controller.expectNone('https://attacker.example/tickets/?offset=1');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Impossibile caricare');
  });
});
