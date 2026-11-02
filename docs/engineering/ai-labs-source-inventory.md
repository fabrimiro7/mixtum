# Inventario sorgenti AI Labs e Documents

I checkout sotto `TEMP/` sono riferimenti locali non versionati, non dipendenze runtime. Gli hash identificano i file esaminati il 2026-10-08.

| Funzione | Sorgente autorevole esaminata | Hash SHA-256 | Destinazione | Accettazione |
|---|---|---|---|---|
| Parsing layout, filtro e crop PDF per area | Fiscally `plugins/fiscally/utils/liteparse_flow_extract.py` | `1b965b2b31beada5a52c63a280e83cc725cc472c049c897d25301689dee1cc54` | Primitive PDF AI Labs | Coordinate 0..1 validate; area invalida fallisce; testo/immagine limitati alla selezione |
| Selettore visuale PDF | Fiscally FE `pdf-area-picker.component.ts` | `f73c0a2d131a0c3adcbff03ea5e5c7a0252e7ec45102039a5f63f15c98d1e639` | Console API/componenti Documents | Cambio pagina e rettangolo normalizzato verificati |
| Flow documentali e modelli | Documents `plugins/flow_manager/models.py` | `c549cfcf3f3a877451d0a858c67d54e69d2419e0300ee74aa1327f4c82a423f7` | Flow AI Labs | Versioni pubblicate, fasi/rami e output strutturati |
| Telemetria chiamate LLM | Documents `plugins/observability/models.py` | `b9a1ba164789611dc3a165df26a79ec68153bf0ef493b8e002208a3034cc0866` | Trace/usage AI Labs | Token, tempi, esito e costo senza contenuti predefiniti |
| Agenti, tool e flow | ISO `plugins/agents/models.py` | `922d807cd76e792e3cf210a884992acb83393ef8e9a3f0b4759429b7389e47a5` | Agent/tool/graph AI Labs | DAG determina l'esecuzione; tool tipizzati; pausa/ripresa |
| Generazioni indice | ISO `plugins/document_manager/rag/generations.py` | `f01f5e16c9658275f60529f0ffdae1e17102a63e5244d2d44edf36d47c24f199` | RAG AI Labs | Cutover atomico; revisione precedente resta attiva su errore |
| Knowledge revision/retrieval | Fiscally `plugins/knowledge/` | checkout `efestodevteam-fiscally-be-3ac35e1ca17b` | RAG AI Labs | Filtri Qdrant e rivalidazione PostgreSQL prima del modello |
| Integrazione Ticket | Ticket legacy, README esaminato | `c6afc3bd488010d7a5e25facbacbb835a2e10c4daa591d0b1da10ed840c04fa5` | Tool pubblico Ticket | Legge solo ticket visibili all'attore; nessuna autorità duplicata |

## Differenze da correggere nel porting

- Il canvas ISO conserva connessioni in metadata, mentre il servizio esegue ruoli specifici e non un DAG generico.
- L'approvazione ISO marca il tool come saltato; AI Labs deve sospendere e riprendere con rivalidazione.
- I connettori ISO Slack/WordPress osservati restituiscono risposte simulate.
- Documents applica un limite di cinque pagine; la nuova elaborazione usa batch espliciti fino al limite del file.
- Il codice Fiscally restituisce tutti i blocchi quando non ricava le dimensioni di un'area; il nuovo contratto fallisce chiuso.
- Fallback provider e thread web osservati non vengono trasferiti: provider e coda devono essere espliciti.

## Provenienza e licenze

I checkout Documents e ISO includono una licenza locale. Prima della distribuzione esterna, verificare proprietà/licenza anche dei checkout Fiscally e Ticket e registrare il risultato nelle note di release. Nessun file in `TEMP` viene copiato integralmente senza revisione e adattamento ai contratti Mixtum.
