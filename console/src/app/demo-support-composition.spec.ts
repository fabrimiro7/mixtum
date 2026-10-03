import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';
import { demoSupportConsoleExtension } from '@mixtum/extension-demo-support-console';
import { consolePlugins, selectConsolePlugins } from '../instance/plugins';

describe('Instance support extension', () => {
  const endpoint = 'http://127.0.0.1:8000/api/demo-support/summary/';
  let workspaces: BehaviorSubject<number | null>;
  let controller: HttpTestingController;

  beforeEach(() => {
    workspaces = new BehaviorSubject<number | null>(null);
    TestBed.configureTestingModule({
      providers: [
        { provide: MIXTUM_API_BASE_URL, useValue: 'http://127.0.0.1:8000' },
        { provide: MIXTUM_SELECTED_WORKSPACE_ID, useValue: workspaces.asObservable() },
        provideHttpClient(), provideHttpClientTesting(),
      ],
    });
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('is selected only by instance composition', () => {
    expect(consolePlugins.map(item => item.id)).toContain('demo_support');
    expect(selectConsolePlugins(['ticket'], [demoSupportConsoleExtension])).toEqual([]);
    expect(demoSupportConsoleExtension.routes[0].path).toBe('support-summary');
  });

  it('renders only the selected workspace result and handles forbidden access', async () => {
    const component = await (demoSupportConsoleExtension.routes[0].loadComponent!() as Promise<Type<unknown>>);
    const fixture = TestBed.createComponent(component);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Seleziona un workspace');
    workspaces.next(1);
    const old = controller.expectOne(endpoint);
    workspaces.next(2);
    controller.expectOne(endpoint).flush({ open: 3, closed: 1 });
    old.flush({ open: 99, closed: 99 });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Ticket aperti: 3');
    expect(fixture.nativeElement.textContent).not.toContain('99');

    workspaces.next(3);
    controller.expectOne(endpoint).flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Accesso non consentito');
  });
});
