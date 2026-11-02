import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { MIXTUM_API_BASE_URL, MIXTUM_SELECTED_WORKSPACE_ID } from '@mixtum/console-api';

interface Version { id:number; filename:string; media_type:string; page_count:number|null; status:string; }
interface DocumentItem { id:number; title:string; visibility:string; versions:Version[]; }
interface Area { x:number; y:number; width:number; height:number; }

@Component({
  selector:'mixtum-documents-page', imports:[FormsModule], changeDetection:ChangeDetectionStrategy.Eager,
  template:`
  <section class="max-w-6xl"><h1 class="text-2xl font-semibold">Documents</h1><p class="mt-1 text-slate-600">Upload privato, selezione aree ed elaborazione con flow AI Labs.</p>
  @if(status==='select'){<p class="mt-6">Seleziona un workspace.</p>}@else if(status==='loading'){<p class="mt-6">Caricamento…</p>}@else if(status==='forbidden'){<p role="alert" class="mt-6 text-amber-800">Accesso negato.</p>}@else if(status==='error'){<p role="alert" class="mt-6 text-red-700">Impossibile caricare Documents.</p>}@else{
    <form class="mt-6 flex flex-wrap gap-3 rounded border p-4" (ngSubmit)="upload()"><input name="title" placeholder="Titolo" required [(ngModel)]="title" class="rounded border px-2"/><select name="visibility" [(ngModel)]="visibility" class="rounded border"><option value="workspace">Workspace</option><option value="restricted">Riservato</option></select><input type="file" (change)="chooseFile($event)" accept=".pdf,.txt,.html,.png,.jpg,.jpeg"/><button [disabled]="!file||!title.trim()" class="text-indigo-700">Carica</button></form>
    <div class="mt-6 grid gap-6 lg:grid-cols-[18rem_1fr]"><ul class="divide-y">@for(document of documents;track document.id){<li><button class="w-full py-3 text-left" (click)="select(document)">{{document.title}}<small class="block text-slate-500">{{document.versions[0]?.filename}}</small></button></li>}</ul>
    @if(selected;as document){<div><h2 class="text-lg font-semibold">{{document.title}}</h2>@if(version?.media_type==='application/pdf'){
      <div class="mt-3 flex gap-2"><label>Pagina <input type="number" min="1" [max]="version.page_count??1" [(ngModel)]="page" (change)="loadPage()" class="w-20 rounded border px-2"/></label><button (click)="clearArea()">Intera pagina</button></div>
      <div #imageBox class="relative mt-3 inline-block max-w-full select-none border" (pointerdown)="startSelection($event)" (pointermove)="moveSelection($event)" (pointerup)="endSelection($event)">@if(pageUrl){<img [src]="pageUrl" alt="Pagina PDF" class="max-h-[65vh] max-w-full" draggable="false"/>}@if(area;as a){<div class="pointer-events-none absolute border-2 border-indigo-600 bg-indigo-200/20" [style.left.%]="a.x*100" [style.top.%]="a.y*100" [style.width.%]="a.width*100" [style.height.%]="a.height*100"></div>}</div>
    }<div class="mt-4 flex gap-3"><button class="rounded bg-indigo-600 px-3 py-2 text-white" (click)="extract()">Estrai {{area?'area':'documento completo'}}</button></div>@if(chunks.length){<ol class="mt-4 space-y-3">@for(chunk of chunks;track $index){<li class="rounded border p-3"><strong>Pagina {{chunk.page}}</strong><pre class="mt-2 whitespace-pre-wrap text-sm">{{chunk.text}}</pre></li>}</ol>}@if(message){<p role="status" class="mt-3">{{message}}</p>}</div>}
    </div>}
  </section>`
})
export class DocumentsPageComponent {
  private readonly http=inject(HttpClient); private readonly base=inject(MIXTUM_API_BASE_URL).replace(/\/$/,''); private readonly destroy=inject(DestroyRef); private request=0;
  @ViewChild('imageBox') imageBox?:ElementRef<HTMLElement>;
  status='select';documents:DocumentItem[]=[];selected:DocumentItem|null=null;version:Version|null=null;title='';visibility='workspace';file:File|null=null;page=1;pageUrl:string|null=null;area:Area|null=null;chunks:{text:string;page:number}[]=[];message='';private origin:{x:number;y:number}|null=null;
  constructor(){inject(MIXTUM_SELECTED_WORKSPACE_ID).pipe(takeUntilDestroyed(this.destroy)).subscribe(id=>{if(id===null){this.status='select';this.documents=[];}else void this.reload();});}
  async reload(){const request=++this.request;this.status='loading';try{const documents=await firstValueFrom(this.http.get<DocumentItem[]>(`${this.base}/api/plugin-documents/documents/`));if(request===this.request){this.documents=documents;this.status='ready';}}catch(error){if(request===this.request)this.status=error instanceof HttpErrorResponse&&[401,403].includes(error.status)?'forbidden':'error';}}
  chooseFile(event:Event){this.file=(event.target as HTMLInputElement).files?.[0]??null;}
  async upload(){if(!this.file||!this.title.trim())return;const data=new FormData();data.append('title',this.title.trim());data.append('visibility',this.visibility);data.append('file',this.file);await firstValueFrom(this.http.post(`${this.base}/api/plugin-documents/documents/`,data));this.title='';this.file=null;await this.reload();}
  select(document:DocumentItem){this.selected=document;this.version=document.versions[0]??null;this.page=1;this.area=null;this.chunks=[];void this.loadPage();}
  async loadPage(){if(this.pageUrl)URL.revokeObjectURL(this.pageUrl);this.pageUrl=null;this.area=null;if(!this.selected||!this.version||this.version.media_type!=='application/pdf')return;try{const blob=await firstValueFrom(this.http.get(`${this.base}/api/plugin-documents/documents/${this.selected.id}/versions/${this.version.id}/pages/${this.page}/`,{responseType:'blob'}));this.pageUrl=URL.createObjectURL(blob);}catch{this.message='Impossibile visualizzare la pagina.';}}
  startSelection(event:PointerEvent){const p=this.point(event);if(!p)return;this.origin=p;this.area={x:p.x,y:p.y,width:0.001,height:0.001};(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);}
  moveSelection(event:PointerEvent){if(!this.origin)return;const p=this.point(event);if(!p)return;this.area={x:Math.min(this.origin.x,p.x),y:Math.min(this.origin.y,p.y),width:Math.max(Math.abs(p.x-this.origin.x),0.001),height:Math.max(Math.abs(p.y-this.origin.y),0.001)};}
  endSelection(event:PointerEvent){this.moveSelection(event);this.origin=null;}
  clearArea(){this.area=null;}
  async extract(){if(!this.selected||!this.version)return;try{const body:Record<string,unknown>={};if(this.version.media_type==='application/pdf'){body['pages']=[this.page];if(this.area)body['area']=this.area;}const result=await firstValueFrom(this.http.post<{chunks:{text:string;page:number}[]}>(`${this.base}/api/plugin-documents/documents/${this.selected.id}/versions/${this.version.id}/extract/`,body));this.chunks=result.chunks;this.message=result.chunks.length?'Estrazione completata.':'Nessun testo: configura OCR/vision per una scansione.';}catch(error){this.message=error instanceof HttpErrorResponse?JSON.stringify(error.error):'Estrazione non riuscita.';}}
  private point(event:PointerEvent){const box=this.imageBox?.nativeElement.getBoundingClientRect();if(!box||box.width===0||box.height===0)return null;return{x:Math.min(1,Math.max(0,(event.clientX-box.left)/box.width)),y:Math.min(1,Math.max(0,(event.clientY-box.top)/box.height))};}
}
