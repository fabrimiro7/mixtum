import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { linksConsolePlugin } from '@mixtum/plugin-links-console';
import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';
import { consolePlugins, selectConsolePlugins } from '../instance/plugins';

describe('Links Console plugin', () => {
  interface LinksPage {
    title: string;
    url: string;
    create(): Promise<void>;
  }

  async function createPage() {
    const component = await (linksConsolePlugin.routes[0].loadComponent!() as Promise<Type<LinksPage>>);
    return TestBed.createComponent(component);
  }

  let workspaceIds: BehaviorSubject<number | null>;
  let controller: HttpTestingController;
  const endpoint = 'http://127.0.0.1:8000/api/plugin-links/links/';

  beforeEach(() => {
    workspaceIds = new BehaviorSubject<number | null>(null);
    TestBed.configureTestingModule({
      providers: [
        { provide: MIXTUM_API_BASE_URL, useValue: 'http://127.0.0.1:8000' },
        { provide: MIXTUM_SELECTED_WORKSPACE_ID, useValue: workspaceIds.asObservable() },
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('registers independently and disappears when disabled', () => {
    expect(consolePlugins.map(plugin => plugin.id)).toContain('links');
    expect(selectConsolePlugins(['plugin_example'], [linksConsolePlugin])).toEqual([]);
    expect(linksConsolePlugin.routes[0].path).toBe('links');
    expect(linksConsolePlugin.navigation).toEqual([{ label: 'Link', path: '/links' }]);
  });

  it('waits for a workspace, then lists and creates links', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Seleziona un workspace');
    controller.expectNone(endpoint);

    workspaceIds.next(7);
    controller.expectOne(endpoint).flush([{ id: 1, title: 'Primo', url: 'https://example.test/1', label: 'altro' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Primo');

    fixture.componentInstance.title = 'Secondo';
    fixture.componentInstance.url = 'https://example.test/2';
    const creating = fixture.componentInstance.create();
    const post = controller.expectOne(endpoint);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ title: 'Secondo', url: 'https://example.test/2' });
    post.flush({ id: 2, title: 'Secondo', url: 'https://example.test/2', label: 'altro' });
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne(endpoint).flush([
      { id: 2, title: 'Secondo', url: 'https://example.test/2', label: 'altro' },
      { id: 1, title: 'Primo', url: 'https://example.test/1', label: 'altro' },
    ]);
    await creating;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Secondo');
  });

  it('drops stale responses after workspace switch', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    const oldRequest = controller.expectOne(endpoint);
    workspaceIds.next(8);
    const newRequest = controller.expectOne(endpoint);
    newRequest.flush([{ id: 8, title: 'Nuovo', url: 'https://example.test/new', label: 'altro' }]);
    oldRequest.flush([{ id: 7, title: 'Vecchio', url: 'https://example.test/old', label: 'altro' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nuovo');
    expect(fixture.nativeElement.textContent).not.toContain('Vecchio');
  });

  it('shows access denied for a forbidden workspace', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    controller.expectOne(endpoint).flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Non hai accesso');
  });
});
