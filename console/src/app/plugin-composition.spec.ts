import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject } from 'rxjs';

import { exampleConsolePlugin } from '@mixtum/plugin-example-console';
import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';
import { consolePlugins, selectConsolePlugins } from '../instance/plugins';
import composition from '../../../mixtum_instance/composition.json';

describe('Example Console plugin', () => {
  interface ExamplePage {
    name: string;
    create(): Promise<void>;
  }

  async function createPage() {
    const component = await (exampleConsolePlugin.routes[0].loadComponent!() as Promise<Type<ExamplePage>>);
    return TestBed.createComponent(component);
  }

  let workspaceIds: BehaviorSubject<number | null>;
  let controller: HttpTestingController;

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

  it('contributes a lazy route and navigation entry', () => {
    expect(consolePlugins.map(plugin => plugin.id)).toEqual([...composition.plugins, ...composition.extensions]);
    expect(selectConsolePlugins([], [exampleConsolePlugin])).toEqual([]);
    expect(exampleConsolePlugin.id).toBe('plugin_example');
    expect(exampleConsolePlugin.routes[0].path).toBe('examples');
    expect(exampleConsolePlugin.navigation).toEqual([{ label: 'Esempi', path: '/examples' }]);
  });

  it('does not load before workspace selection, then lists and creates items', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Seleziona un workspace');
    controller.expectNone('http://127.0.0.1:8000/api/plugin-example/examples/');

    workspaceIds.next(7);
    const list = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    expect(list.request.method).toBe('GET');
    list.flush([{ id: 1, name: 'Primo' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Primo');

    fixture.componentInstance.name = 'Secondo';
    const creating = fixture.componentInstance.create();
    const post = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    expect(post.request.body).toEqual({ name: 'Secondo' });
    post.flush({ id: 2, name: 'Secondo' });
    await new Promise(resolve => setTimeout(resolve, 0));
    controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/').flush([
      { id: 2, name: 'Secondo' }, { id: 1, name: 'Primo' },
    ]);
    await creating;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Secondo');
  });

  it('drops stale results when the workspace changes', async () => {
    const fixture = await createPage();
    fixture.detectChanges();
    workspaceIds.next(7);
    const oldRequest = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    workspaceIds.next(8);
    const newRequest = controller.expectOne('http://127.0.0.1:8000/api/plugin-example/examples/');
    newRequest.flush([{ id: 8, name: 'Nuovo' }]);
    oldRequest.flush([{ id: 7, name: 'Vecchio' }]);
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nuovo');
    expect(fixture.nativeElement.textContent).not.toContain('Vecchio');
  });
});
