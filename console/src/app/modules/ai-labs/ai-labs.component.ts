import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/services/auth.service';
import { MIXTUM_CONFIG } from '../../core/runtime-config';

interface GraphNode { id: string; type: string; config: Record<string, unknown>; }
interface GraphEdge { from: string; to: string; when?: boolean; }
interface Flow { id: number; name: string; slug: string; description: string; draft_graph: { nodes: GraphNode[]; edges: GraphEdge[]; output?: string }; published_version: { version: number } | null; }
interface Run { id: string; source_product: string; status: string; total_tokens: number | null; cost_microunits: number | null; error_message: string; created_at: string; }
type PageState = 'select-workspace' | 'loading' | 'ready' | 'forbidden' | 'error';

@Component({
  selector: 'app-ai-labs',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.Eager,
  template: `
    <section class="max-w-6xl" aria-labelledby="ai-labs-title">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div><h1 id="ai-labs-title" class="text-2xl font-semibold">AI Labs</h1><p class="mt-1 text-slate-600">Agenti, flow, knowledge base, consumi e tracce.</p></div>
        <button type="button" class="rounded border px-3 py-2" (click)="reload()">Aggiorna</button>
      </div>
      @if (state === 'select-workspace') { <p class="mt-6">Seleziona un workspace.</p> }
      @else if (state === 'loading') { <p class="mt-6">Caricamento…</p> }
      @else if (state === 'forbidden') { <p role="alert" class="mt-6 text-amber-800">Non puoi configurare AI Labs in questo workspace.</p> }
      @else if (state === 'error') { <p role="alert" class="mt-6 text-red-700">Impossibile caricare AI Labs.</p> }
      @else {
        <div class="mt-6 flex gap-2 border-b">
          @for (value of ['flows', 'runs']; track value) {
            <button type="button" class="px-3 py-2" [class.border-b-2]="tab === value" (click)="tab = value">{{ value === 'flows' ? 'Flow builder' : 'Esecuzioni' }}</button>
          }
        </div>
        @if (tab === 'flows') {
          <div class="mt-5 grid gap-6 lg:grid-cols-[18rem_1fr]">
            <aside>
              <form class="grid gap-2 rounded border p-3" (ngSubmit)="createFlow()">
                <label for="new-flow">Nuovo flow</label><input id="new-flow" name="newFlow" class="rounded border px-2 py-1" [(ngModel)]="newFlowName" />
                <button class="text-left text-indigo-700" [disabled]="!newFlowName.trim()">Crea</button>
              </form>
              <ul class="mt-3 divide-y">@for (flow of flows; track flow.id) {<li><button type="button" class="w-full px-2 py-3 text-left" (click)="select(flow)">{{flow.name}} @if(flow.published_version){<small>v{{flow.published_version.version}}</small>}</button></li>}</ul>
            </aside>
            @if (selected; as flow) {
              <div>
                <div class="flex flex-wrap gap-2"><input class="rounded border px-2 py-1" [(ngModel)]="flow.name" /><button class="text-indigo-700" (click)="save()">Salva bozza</button><button class="text-emerald-700" (click)="publish()">Pubblica versione</button></div>
                <div class="mt-5 rounded border bg-slate-50 p-4">
                  <h2 class="font-semibold">Grafo eseguibile</h2>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    @for (node of flow.draft_graph.nodes; track node.id) {
                      <article class="rounded border bg-white p-3"><div class="flex justify-between"><strong>{{node.id}}</strong><button class="text-red-700" (click)="removeNode(node.id)">×</button></div><span class="text-sm text-slate-600">{{node.type}}</span><textarea aria-label="Configurazione JSON" class="mt-2 h-28 w-full rounded border p-2 font-mono text-xs" [ngModel]="json(node.config)" (ngModelChange)="setConfig(node, $event)"></textarea></article>
                    }
                  </div>
                  <form class="mt-4 flex flex-wrap gap-2" (ngSubmit)="addNode()"><input name="nodeId" placeholder="id nodo" class="rounded border px-2" [(ngModel)]="nodeId"/><select name="nodeType" class="rounded border px-2" [(ngModel)]="nodeType">@for(type of nodeTypes; track type){<option [value]="type">{{type}}</option>}</select><button class="text-indigo-700">Aggiungi nodo</button></form>
                  <h3 class="mt-5 font-semibold">Collegamenti</h3><ul>@for(edge of flow.draft_graph.edges; track edge.from + edge.to){<li>{{edge.from}} → {{edge.to}} <button class="text-red-700" (click)="removeEdge(edge)">rimuovi</button></li>}</ul>
                  <form class="mt-3 flex gap-2" (ngSubmit)="addEdge()"><select name="edgeFrom" [(ngModel)]="edgeFrom" class="rounded border">@for(node of flow.draft_graph.nodes; track node.id){<option [value]="node.id">{{node.id}}</option>}</select><span>→</span><select name="edgeTo" [(ngModel)]="edgeTo" class="rounded border">@for(node of flow.draft_graph.nodes; track node.id){<option [value]="node.id">{{node.id}}</option>}</select><button class="text-indigo-700">Collega</button></form>
                </div>
                @if(message){<p role="status" class="mt-3">{{message}}</p>}
              </div>
            } @else { <p>Seleziona o crea un flow.</p> }
          </div>
        } @else {
          <div class="mt-5 overflow-x-auto"><table class="w-full text-left"><thead><tr><th>Data</th><th>Prodotto</th><th>Stato</th><th>Token</th><th>Costo µ</th></tr></thead><tbody>@for(run of runs; track run.id){<tr class="border-t"><td class="py-2">{{run.created_at}}</td><td>{{run.source_product}}</td><td>{{run.status}}</td><td>{{run.total_tokens ?? '—'}}</td><td>{{run.cost_microunits ?? 'sconosciuto'}}</td></tr>}</tbody></table></div>
        }
      }
    </section>
  `,
})
export class AiLabsComponent {
  private readonly http = inject(HttpClient); private readonly auth = inject(AuthService); private readonly destroy = inject(DestroyRef);
  private readonly base = inject(MIXTUM_CONFIG).apiBaseUrl.replace(/\/$/, '');
  state: PageState = 'select-workspace'; tab = 'flows'; flows: Flow[] = []; runs: Run[] = []; selected: Flow | null = null; newFlowName = ''; nodeId = ''; nodeType = 'input'; edgeFrom = ''; edgeTo = ''; message = '';
  readonly nodeTypes = ['input', 'llm', 'tool', 'condition', 'merge', 'validate_json', 'output'];
  constructor(){this.auth.selectedWorkspaceId$.pipe(takeUntilDestroyed(this.destroy)).subscribe(() => void this.reload());}
  async reload(){if(this.auth.selectedWorkspaceId()===null){this.state='select-workspace';return;} this.state='loading';try{const [flows,runs]=await Promise.all([firstValueFrom(this.http.get<Flow[]>(`${this.base}/api/ai-labs/flows/`)),firstValueFrom(this.http.get<Run[]>(`${this.base}/api/ai-labs/runs/`))]);this.flows=flows;this.runs=runs;this.selected=this.selected?flows.find(f=>f.id===this.selected?.id)??null:null;this.state='ready';}catch(error){this.state=error instanceof HttpErrorResponse&&[401,403].includes(error.status)?'forbidden':'error';}}
  select(flow: Flow){this.selected=structuredClone(flow);this.edgeFrom=flow.draft_graph.nodes[0]?.id??'';this.edgeTo=flow.draft_graph.nodes[1]?.id??'';}
  async createFlow(){const name=this.newFlowName.trim();if(!name)return;const slug=name.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,150)||`flow-${Date.now()}`;const flow=await firstValueFrom(this.http.post<Flow>(`${this.base}/api/ai-labs/flows/`,{name,slug,draft_graph:{nodes:[{id:'input',type:'input',config:{}},{id:'output',type:'output',config:{value:'{{ input }}'}}],edges:[{from:'input',to:'output'}],output:'output'}}));this.newFlowName='';await this.reload();this.select(flow);}
  async save(){if(!this.selected)return;try{const saved=await firstValueFrom(this.http.patch<Flow>(`${this.base}/api/ai-labs/flows/${this.selected.id}/`,{name:this.selected.name,draft_graph:this.selected.draft_graph}));this.selected=structuredClone(saved);this.message='Bozza salvata e validata dal backend.';}catch(error){this.message=this.error(error);}}
  async publish(){if(!this.selected)return;try{await firstValueFrom(this.http.post(`${this.base}/api/ai-labs/flows/${this.selected.id}/publish/`,{}));this.message='Versione immutabile pubblicata.';await this.reload();}catch(error){this.message=this.error(error);}}
  addNode(){if(!this.selected||!this.nodeId.match(/^[a-z][a-z0-9_-]*$/)||this.selected.draft_graph.nodes.some(n=>n.id===this.nodeId))return;this.selected.draft_graph.nodes.push({id:this.nodeId,type:this.nodeType,config:{}});this.nodeId='';}
  removeNode(id:string){if(!this.selected)return;this.selected.draft_graph.nodes=this.selected.draft_graph.nodes.filter(n=>n.id!==id);this.selected.draft_graph.edges=this.selected.draft_graph.edges.filter(e=>e.from!==id&&e.to!==id);}
  addEdge(){if(!this.selected||!this.edgeFrom||!this.edgeTo||this.edgeFrom===this.edgeTo)return;if(!this.selected.draft_graph.edges.some(e=>e.from===this.edgeFrom&&e.to===this.edgeTo))this.selected.draft_graph.edges.push({from:this.edgeFrom,to:this.edgeTo});}
  removeEdge(edge:GraphEdge){if(this.selected)this.selected.draft_graph.edges=this.selected.draft_graph.edges.filter(item=>item!==edge);}
  json(value:unknown){return JSON.stringify(value,null,2);} setConfig(node:GraphNode,value:string){try{node.config=JSON.parse(value);this.message='';}catch{this.message='JSON del nodo non valido.';}}
  private error(error:unknown){return error instanceof HttpErrorResponse?(error.error?.detail??JSON.stringify(error.error)):'Operazione non riuscita.';}
}
