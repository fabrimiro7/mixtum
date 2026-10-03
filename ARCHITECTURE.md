# Mixtum Framework — Piano di evoluzione architetturale

## Documento di riferimento

**Obiettivo:** trasformare Mixtum da applicazione/framework cresciuto per moduli successivi in una vera **application platform modulare**, mantenibile, componibile e aggiornabile senza fork continui per cliente o progetto.

Il modello target è:

> **Modular monolith a livello applicativo + servizi infrastrutturali esterni componibili + plugin di prodotto + extension specifiche di istanza.**

---

# 1. Contesto attuale

Mixtum sta evolvendo verso una piattaforma comune utilizzabile per scenari e prodotti diversi.

Le principali evoluzioni infrastrutturali già in corso sono:

- autenticazione centralizzata tramite **Keycloak**;
- supporto a deployment tramite **Docker** e **Kubernetes**;
- separazione tra:
  - una **Mixtum Console**, uguale e condivisa tra le varie installazioni;
  - un **Public Frontend**, personalizzabile di volta in volta;
- introduzione di:
  - workspace;
  - branding dinamico;
  - RAG;
  - Qdrant;
  - agenti LLM;
  - tool calling;
  - osservabilità;
  - primitive AI;
  - provider LLM locali o remoti;
- utilizzo di componenti infrastrutturali quali:
  - PostgreSQL;
  - Redis;
  - Celery;
  - Keycloak;
  - Qdrant;
  - vLLM;
  - Docker;
  - Kubernetes.

Gli attuali principali scenari applicativi sono i seguenti.

---

# 2. Verticali attuali

## 2.1 Mixtum Ticket

Sistema di ticketing per:

- supporto;
- customer care;
- gestione ticket;
- assegnazioni;
- stati;
- priorità;
- workflow;
- interazioni con il cliente.

Nell'installazione EfestoDev sono state inoltre aggiunte varie funzionalità specifiche:

- gestione di progetti collegati ai ticket;
- task manager;
- repository information;
- conteggio economico dei ticket;
- integrazione con abbonamenti;
- funzionalità finanziarie.

Queste ultime non sono necessariamente funzionalità generiche di Mixtum Ticket, ma customizzazioni nate per esigenze EfestoDev.

---

## 2.2 Mixtum Documents

Sistema documentale con:

- gestione cartelle;
- gestione documenti;
- upload;
- lettura dei documenti;
- estrazione informazioni tramite AI;
- elaborazioni tramite LLM;
- workflow automatici;
- operazioni AI sui documenti;
- RAG;
- ricerca semantica.

È uno dei moduli già maggiormente utilizzati.

---

## 2.3 Mixtum Events

Verticale per:

- prenotazione di esperienze;
- eventi;
- disponibilità;
- prenotazioni;
- eventualmente checkout e pagamenti.

Concettualmente è paragonabile a una piattaforma simile a GetYourGuide.

---

## 2.4 Mixtum Academy

Verticale LMS / e-learning per:

- corsi;
- lezioni;
- studenti;
- docenti;
- quiz;
- progressi;
- contenuti didattici;
- AI applicata all'apprendimento;
- tutor AI;
- supporto personalizzato;
- RAG sui contenuti formativi.

---

# 3. Problema architetturale

Il problema principale non è la quantità di funzionalità.

Il problema è che oggi tendono a convivere sullo stesso piano:

- framework;
- infrastruttura;
- logica trasversale;
- verticali;
- funzionalità riutilizzabili;
- customizzazioni cliente;
- componenti AI;
- deployment;
- integrazioni.

La conseguenza è che alcune componenti tendono a essere:

- duplicate;
- riscritte;
- forkate;
- adattate progetto per progetto.

Un esempio evidente è quello degli **AI Agent**.

Se ogni verticale implementa autonomamente:

- provider;
- agent runtime;
- tool registry;
- RAG;
- tracing;
- prompt;
- logging;
- structured output;
- cost accounting;

il framework tenderà inevitabilmente a divergere.

La soluzione proposta è introdurre confini architetturali molto più rigidi.

---

# 4. Architettura target

Mixtum dovrebbe essere suddiviso in quattro livelli principali:

```text
Mixtum
│
├── Core
│
├── Platform Capabilities
│
├── Product Plugins
│
└── Project / Instance Extensions
```

La distinzione deve essere strutturale e non puramente organizzativa.

---

# 5. Livello 1 — Mixtum Core

Il Core deve essere piccolo, stabile e il più possibile indipendente dai verticali.

Regola:

> Se una funzionalità non serve potenzialmente a quasi ogni distribuzione Mixtum, probabilmente non appartiene al Core.

Il Core non deve conoscere:

- Ticket;
- Documents;
- Academy;
- Events;
- customizzazioni EfestoDev;
- customizzazioni cliente.

Il Core può invece contenere:

```text
core/
├── workspace
├── identity integration
├── authorization primitives
├── branding
├── configuration
├── feature flags
├── event system
├── audit
├── plugin registry
├── extension registry
└── shared domain primitives
```

Il Core deve fornire i meccanismi, non i casi d'uso verticali.

---

# 6. Livello 2 — Platform Capabilities

Le Platform Capabilities sono servizi riutilizzabili da più plugin.

Esempi:

```text
platform/
├── ai
├── payments
├── notifications
├── storage
├── search
├── files
├── billing primitives
└── integrations
```

Non sono necessariamente obbligatorie per ogni installazione.

Sono capability attivabili e configurabili.

---

# 7. Livello 3 — Product Plugins

I principali verticali diventano plugin di prodotto:

```text
plugins/
├── ticket
├── documents
├── academy
├── events
└── project-manager
```

Ogni plugin deve poter essere:

- installato;
- abilitato;
- disabilitato;
- versionato;
- aggiornato indipendentemente;
- configurato;
- integrato con altri plugin tramite API o eventi.

Un'installazione può quindi avere:

```yaml
plugins:
  - ticket
  - academy
```

oppure:

```yaml
plugins:
  - documents
```

oppure:

```yaml
plugins:
  - ticket
  - documents
  - academy
  - events
```

Tutti possono coesistere nella stessa istanza Mixtum.

---

# 8. Livello 4 — Project / Instance Extensions

Le personalizzazioni specifiche non devono modificare direttamente i plugin standard.

Esempio EfestoDev:

```text
extensions/
└── efestodev/
    ├── ticket_project_integration
    ├── ticket_finance
    ├── subscription_integration
    ├── repository_info
    └── internal_workflows
```

Quindi invece di modificare:

```text
mixtum-ticket
```

si crea:

```text
efestodev-ticket-extension
```

La regola fondamentale deve essere:

```text
CORE
 ↑
PLUGIN
 ↑
PROJECT EXTENSION
```

Il Core non dipende dai plugin.

Il plugin dipende dal Core.

L'extension può dipendere da Core e plugin.

---

# 9. Obiettivo principale: eliminare i fork

Lo scenario da evitare è:

```text
clone repository
↓
modifica Ticket
↓
modifica AI
↓
modifica Documents
↓
customizza per cliente
↓
fork
↓
aggiornamento Mixtum difficile
```

Lo scenario target è:

```text
Mixtum Platform
↓
selezione plugin
↓
configurazione capability
↓
custom extension
↓
branding
↓
public frontend
↓
deploy
```

Quindi una nuova installazione deve essere principalmente:

- configurazione;
- composizione;
- extension;
- branding;
- frontend pubblico.

Non un fork del framework.

---

# 10. Mixtum come piattaforma e non come singola applicazione

L'evoluzione concettuale è:

```text
Mixtum = software
```

verso:

```text
Mixtum = piattaforma con cui costruire software
```

I prodotti:

- Ticket;
- Documents;
- Academy;
- Events;

diventano distribuzioni / verticali costruiti sopra Mixtum.

---

# 11. Esempio di installazioni diverse

## Cliente A

```text
Mixtum
├── Ticket
└── Documents
```

## Cliente B

```text
Mixtum
├── Academy
├── Documents
└── Payments
```

## Cliente C

```text
Mixtum
├── Ticket
├── Academy
├── Events
├── Documents
└── custom-plugin-cliente-c
```

Il framework di base resta lo stesso.

Cambiano:

- plugin abilitati;
- configurazione;
- branding;
- extension;
- public frontend;
- infrastruttura opzionale.

---

# 12. Modular monolith

Per il momento non conviene separare i verticali in microservizi indipendenti.

Non è consigliato avere:

```text
Mixtum Ticket
    ↓ HTTP
Mixtum Documents
    ↓ HTTP
Mixtum Academy
```

solo perché sono domini diversi.

Questo introdurrebbe:

- autenticazione distribuita;
- propagazione delle autorizzazioni;
- retry;
- failure di rete;
- compatibilità tra versioni;
- transazioni distribuite;
- deployment ordering;
- observability distribuita;
- maggior costo operativo.

La soluzione raccomandata è:

> **Modular monolith con boundary rigidi.**

Esempio:

```text
                    ┌──────────────────────────┐
                    │       MIXTUM APP         │
                    │                          │
                    │ Ticket                   │
                    │ Documents                │
                    │ Academy                  │
                    │ Events                   │
                    │ AI Runtime               │
                    │ Payments                 │
                    │ Workspace                │
                    └────────────┬─────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                 │
           PostgreSQL          Redis            Keycloak

                  optional infrastructure

               Qdrant        vLLM       S3/MinIO
```

---

# 13. Quando separare realmente un servizio

La separazione deve essere giustificata da motivi operativi reali.

Ha senso separare quando esiste almeno uno di questi motivi:

| Motivo | Separazione |
|---|---|
| carico molto diverso | sì |
| scaling indipendente | sì |
| sicurezza diversa | sì |
| trust boundary differente | sì |
| lifecycle di deploy indipendente | sì |
| database realmente indipendente | sì |
| servizio usato da molte istanze Mixtum | possibile |
| modulo molto grande | non sufficiente |
| dominio diverso | non sufficiente |
| moda dei microservizi | no |

Principio:

> Preparare le interfacce affinché una capability possa essere estratta in futuro, senza estrarla prima che serva.

---

# 14. Keycloak

Keycloak può e dovrebbe essere il punto centrale dell'identità.

È sensato usarlo in modo trasversale per:

- Django;
- Console Angular;
- Public Frontend;
- eventuali app mobile;
- altri client.

Architettura:

```text
                  Keycloak
                     │
         ┌───────────┼───────────┐
         │           │           │
       Django     Console     Public FE
         │         Angular      Angular
         │
      APIs
```

Questo permette:

- Single Sign-On;
- una sola identità;
- sessione centralizzata;
- gestione utenti centralizzata;
- MFA;
- federation LDAP / Active Directory;
- OIDC;
- OAuth2;
- gruppi;
- ruoli.

---

# 15. Keycloak come fonte di verità

Keycloak può essere la fonte primaria per:

```text
utente
email
nome
cognome
username
stato account
MFA
sessioni
gruppi
realm roles
client roles
identity federation
```

Esempi di ruoli:

```text
mixtum-admin
mixtum-user
workspace-admin

ticket-manager
ticket-agent

academy-manager
academy-teacher
academy-student

documents-manager
documents-user
```

Il token può contenere questi ruoli e gli stessi possono essere utilizzati da:

- Django;
- Console Angular;
- Public Frontend.

---

# 16. Autenticazione vs autorizzazione applicativa

La distinzione importante è:

```text
Authentication
"Chi sei?"
```

contro:

```text
Authorization
"Cosa puoi fare?"
```

Keycloak può gestire molto bene i ruoli globali.

Bisogna invece valutare con cautela se spostare dentro Keycloak ogni autorizzazione fine-grained legata alle risorse di dominio.

Esempi:

```text
Mario può leggere documento 438
Mario può modificare cartella A
Laura è docente del corso 52
Giovanni è studente del corso 52
Operatore A vede solo ticket assegnati a lui
Manager B vede tutti i ticket del workspace
```

Trasformare tutto in ruoli del tipo:

```text
document-438-read
document-438-write
course-52-teacher
ticket-project-18-manager
```

porterebbe Keycloak a diventare anche database del dominio applicativo.

Questo può aumentare:

- complessità;
- cardinalità dei ruoli;
- sincronizzazione;
- coupling con Keycloak;
- difficoltà di query;
- difficoltà di migrazione.

---

# 17. Modello ibrido consigliato

Keycloak:

```text
Identity
Global roles
Client roles
Groups
SSO
Sessions
MFA
Federation
```

Django / Mixtum:

```text
WorkspaceMembership
CourseMembership
DocumentPermission
TicketAssignment
ProjectMembership
ResourceOwnership
Domain-specific ACL
```

Esempio:

```python
user = keycloak_user(request)

if not user.has_role("documents-manager"):
    deny()

document = Document.objects.get(pk=438)

if not document.workspace.user_can_access(user):
    deny()
```

---

# 18. Angular e Keycloak

Entrambi i frontend possono utilizzare Keycloak direttamente.

La Console può utilizzare ruoli e claim per:

- routing;
- menu;
- visibilità;
- UX;
- funzionalità disponibili.

Esempio:

```text
ticket-agent       = true
documents-manager  = true
academy-manager    = false
```

La UI mostra solo le sezioni coerenti.

Tuttavia:

> Il frontend non deve essere considerato il punto di enforcement della sicurezza.

La sicurezza reale deve essere sempre validata dalle API Django.

Quindi:

```text
Keycloak
   │
   ├── Angular → UX / routing / feature visibility
   │
   └── Django → authorization enforcement
```

---

# 19. Workspace

Workspace dovrebbe diventare una delle entità centrali di Mixtum.

Schema concettuale:

```text
User
  ↓
WorkspaceMembership
  ↓
Workspace
  ↓
Plugin resources
```

Le risorse dei plugin dovrebbero essere normalmente workspace-scoped.

Esempio:

```text
Ticket     → workspace scoped
Documents  → workspace scoped
Academy    → workspace scoped
Events     → workspace scoped
Branding   → workspace scoped
Payments   → workspace scoped
```

Ogni plugin dovrebbe dichiarare se una risorsa è:

- global;
- workspace-scoped;
- user-scoped.

---

# 20. Workspace e Keycloak

Una possibile struttura Keycloak può essere:

```text
/workspaces/efestodev
/workspaces/cliente-a
/workspaces/cliente-b
```

Eventualmente:

```text
/workspaces/cliente-a/admins
/workspaces/cliente-a/users
```

È comunque utile mantenere anche una rappresentazione applicativa locale:

```python
WorkspaceMembership(
    workspace_id,
    keycloak_user_id,
    role,
    status,
    invited_by,
    joined_at,
    ...
)
```

Perché il dominio Mixtum può aver bisogno di:

- billing seat;
- data ingresso;
- inviti;
- stato membership;
- limiti;
- preferenze;
- plugin abilitati;
- configurazioni.

---

# 21. Branding

Il branding dovrebbe essere una capability centrale del Core.

Esempio:

```text
WorkspaceTheme
```

con dati del tipo:

```json
{
  "logo": "...",
  "primary": "...",
  "secondary": "...",
  "surface": "...",
  "font": "...",
  "borderRadius": "...",
  "darkMode": true
}
```

La Console può tradurre queste proprietà in CSS variables:

```css
--mixtum-primary
--mixtum-secondary
--mixtum-surface
--mixtum-radius
```

Il Public Frontend può:

- usare lo stesso sistema;
- usarne solo una parte;
- ignorarlo completamente.

---

# 22. Mixtum Console

La Console dovrebbe essere unica e comune a tutte le installazioni.

È la shell amministrativa di Mixtum.

Un plugin può registrare:

```text
routes
menu items
permissions
dashboard widgets
settings pages
workspace sections
actions
```

Esempio con Ticket:

```text
Support
├── Inbox
├── Ticket
└── SLA
```

Esempio con Academy:

```text
Academy
├── Corsi
├── Lezioni
├── Studenti
└── Quiz
```

---

# 23. Plugin frontend

Per Angular conviene evitare inizialmente un plugin system eccessivamente dinamico.

Non è necessario partire subito con:

- microfrontend runtime;
- Module Federation complessa;
- pacchetti caricati da server remoti.

Meglio partire con composizione a build time:

```text
plugin manifest
       ↓
plugin registry
       ↓
Angular routes
       ↓
lazy loaded modules
```

In futuro, se esisterà un vero marketplace di plugin di terze parti, sarà possibile valutare runtime plugin loading.

---

# 24. Public Frontend

Il Public Frontend deve restare separato dalla Console.

Architettura:

```text
               MIXTUM APIs
                   │
          ┌────────┴────────┐
          │                 │
   Mixtum Console      Public Frontend
     universale            custom
```

Il Public Frontend può essere:

- Angular;
- Next.js;
- Nuxt;
- Ionic;
- app mobile;
- WordPress;
- altro client.

Non dovrebbe dipendere internamente dal backend.

Deve consumare API stabili.

---

# 25. SDK Mixtum

Ha senso introdurre:

```text
@mixtum/sdk
```

eventualmente generato a partire dalla OpenAPI del backend.

Questo facilita:

- frontend custom;
- applicazioni mobile;
- integrazioni;
- compatibilità tra versioni.

---

# 26. AI Runtime

Gli agenti AI non dovrebbero essere implementati separatamente all'interno dei verticali.

Da evitare:

```text
TicketAgentSystem
DocumentsAgentSystem
AcademyAgentSystem
EventsAgentSystem
```

con ognuno:

- provider;
- tool calling;
- RAG;
- tracing;
- logging;
- prompts;
- memory;
- model routing.

Serve invece un unico:

```text
Mixtum AI Runtime
```

---

# 27. Componenti dell'AI Runtime

L'AI Runtime dovrebbe contenere almeno:

```text
Provider Registry
Agent Runtime
Tool Registry
Prompt Registry
RAG API
Embeddings API
Model Router
Structured Output
Observability
Tracing
Usage Accounting
Cost Accounting
Guardrails
Conversation Runtime
Evaluation hooks
```

---

# 28. Registrazione degli agenti da parte dei plugin

Mixtum Documents:

```python
register_agent(DocumentAnalysisAgent)
register_tool(ReadDocumentTool)
register_tool(ExtractInvoiceTool)
register_retriever(DocumentRetriever)
```

Mixtum Academy:

```python
register_agent(TutorAgent)
register_tool(GetCourseContentTool)
register_tool(GetStudentProgressTool)
```

Mixtum Ticket:

```python
register_agent(SupportAgent)
register_tool(SearchTicketsTool)
register_tool(GetCustomerHistoryTool)
```

I verticali dichiarano ciò che espongono.

Il runtime che esegue gli agenti resta unico.

---

# 29. Provider LLM

Il codice applicativo non deve sapere quale provider concreto viene utilizzato.

Interfaccia:

```python
llm.complete(...)
```

Implementazioni possibili:

```text
OpenAIProvider
RegoloProvider
AnthropicProvider
OllamaProvider
VLLMProvider
OpenAICompatibleProvider
```

Questo permette di cambiare provider senza modificare Ticket, Documents, Academy o Events.

---

# 30. Vector Store

Stesso principio per il vector database.

Interfaccia:

```python
vector_store.search(...)
```

Implementazioni:

```text
QdrantVectorStore
PgVectorVectorStore
ExternalVectorStore
```

Il codice applicativo non deve dipendere direttamente da Qdrant.

---

# 31. Qdrant e vLLM non sono plugin applicativi

Qdrant e vLLM sono implementazioni infrastrutturali di capability.

Quindi:

```text
RAG
  ↓
VectorStore abstraction
  ↓
Qdrant
```

e:

```text
LLM
  ↓
LLMProvider abstraction
  ↓
vLLM / Regolo / OpenAI / Ollama
```

Questo è importante per rendere il deployment realmente configurabile.

---

# 32. Deployment opzionale

Esempio installazione con Regolo e senza RAG:

```yaml
ai:
  enabled: true

  llm:
    provider: regolo

  rag:
    enabled: false
```

Deployment:

```text
Postgres   ✓
Redis      ✓
Keycloak   ✓
Qdrant     ✗
vLLM       ✗
```

---

# 33. Deployment con AI locale

```yaml
ai:
  enabled: true

  llm:
    provider: vllm

  rag:
    enabled: true
    vector_store: qdrant
```

Deployment:

```text
Postgres   ✓
Redis      ✓
Keycloak   ✓
Qdrant     ✓
vLLM       ✓
```

---

# 34. mixtum.yaml

È consigliato introdurre un manifest principale della distribuzione.

Esempio:

```yaml
project:
  name: efestodev
  environment: production

platform:
  version: "4.0"

plugins:
  - ticket
  - documents
  - project-manager
  - efestodev-ticket-extension

platform_capabilities:
  ai:
    enabled: true

    provider:
      type: openai-compatible
      name: regolo

    rag:
      enabled: true
      backend: qdrant

  payments:
    enabled: true
    provider: stripe

  notifications:
    enabled: true

infrastructure:
  postgres: true
  redis: true

  qdrant:
    deploy: auto

  vllm:
    deploy: auto
```

---

# 35. Dependency resolution

Mixtum può costruire un dependency graph.

Esempio:

```text
documents
    ↓
rag enabled
    ↓
vector backend = qdrant
    ↓
Qdrant required
```

Quindi il deployment engine abilita automaticamente Qdrant.

Oppure:

```text
provider = regolo
```

non richiede vLLM.

L'obiettivo è fare in modo che la stessa configurazione possa generare:

- Docker Compose;
- Helm values;
- manifest Kubernetes;
- environment configuration.

---

# 36. Plugin manifest

Ogni plugin dovrebbe avere un manifest.

Esempio Documents:

```yaml
name: documents
version: 3.2.0

requires:
  mixtum-core: ">=4.0"

capabilities:
  storage: required
  ai: optional
  rag: optional

backend:
  django_app: mixtum_documents

frontend:
  console_routes: true

permissions:
  - documents.read
  - documents.write
  - documents.admin
```

Academy:

```yaml
name: academy
version: 1.8.0

requires:
  mixtum-core: ">=4.0"

capabilities:
  ai: optional
  payments: optional
  video: optional
```

---

# 37. Plugin dependencies

Le dipendenze dirette tra plugin devono essere limitate.

Da evitare:

```python
from mixtum_documents.models import ...
```

dentro Ticket.

Meglio utilizzare:

- API interne;
- service interface;
- event bus;
- capability registry.

---

# 38. Event bus interno

Esempio:

```python
emit(
    "ticket.resolved",
    ticket_id=123,
    user_id=456
)
```

Academy può reagire:

```python
@listen("ticket.resolved")
def suggest_training(event):
    ...
```

Questo permette composizione senza coupling diretto.

---

# 39. Ticket + Academy nella stessa istanza

Sì: i due verticali devono poter convivere nello stesso Mixtum.

Esempio:

```yaml
plugins:
  - ticket
  - academy
```

L'istanza condividerebbe:

```text
Postgres
Redis
Keycloak
Workspace
Branding
Console
AI Runtime
Payments
Notifications
```

La Console può mostrare:

```text
Dashboard

Support
├── Ticket
├── SLA
└── Clienti

Academy
├── Corsi
├── Lezioni
├── Studenti
└── Quiz

Impostazioni
├── Workspace
├── Utenti
└── Branding
```

L'utente effettua un solo login.

---

# 40. Interazione tra Ticket e Academy

La coesistenza permette casi d'uso interessanti.

Esempio:

```text
Ticket:
"Come configuro il prodotto X?"
```

Il sistema può rilevare che esiste un contenuto Academy pertinente.

Workflow:

```text
TicketResolved
      ↓
Event Bus
      ↓
Academy
      ↓
Suggerimento corso / lezione
```

Senza necessità di una chiamata HTTP tra due applicazioni indipendenti.

---

# 41. Mixtum Ticket generico vs installazione EfestoDev

Mixtum Ticket deve rimanere un prodotto riutilizzabile.

Core Ticket:

```text
apertura ticket
stato
priorità
assegnazione
commenti
SLA
customer care
```

EfestoDev Extension:

```text
ticket ↔ progetto
task management custom
repository information
contabilità ticket
abbonamenti
workflow interni
```

Quindi:

```text
mixtum-ticket
```

non dovrebbe contenere logica specifica EfestoDev.

---

# 42. Repository structure proposta

Una possibile struttura è:

```text
mixtum/
│
├── core/
│   ├── workspace
│   ├── authorization
│   ├── branding
│   ├── configuration
│   ├── audit
│   ├── events
│   └── extensions
│
├── platform/
│   ├── ai
│   │   ├── agents
│   │   ├── tools
│   │   ├── providers
│   │   ├── rag
│   │   └── observability
│   │
│   ├── payments
│   ├── notifications
│   ├── storage
│   └── search
│
├── plugins/
│   ├── ticket
│   ├── documents
│   ├── academy
│   ├── events
│   └── project-manager
│
├── infrastructure/
│   ├── docker
│   ├── kubernetes
│   ├── keycloak
│   ├── postgres
│   ├── redis
│   ├── qdrant
│   └── vllm
│
├── console/
│
└── sdk/
```

Le installazioni possono invece vivere separatamente:

```text
projects/
└── efestodev/
    ├── mixtum.yaml
    ├── backend_extensions/
    ├── console_extensions/
    ├── branding/
    └── public-frontend/
```

---

# 43. Versionamento

Ogni componente dovrebbe avere un proprio ciclo di versione.

Esempio:

```text
mixtum-platform   4.3
mixtum-ticket     2.5
mixtum-documents  3.1
mixtum-academy    1.8
mixtum-events     1.2
```

Distribuzione cliente:

```yaml
platform: "4.3"

plugins:
  ticket: "2.5"
  academy: "1.8"
  documents: "3.1"
```

---

# 44. Regole di dipendenza

Le dipendenze devono puntare verso il basso.

Corretto:

```text
Extension → Plugin → Platform → Core
```

Da evitare:

```text
Core → Ticket
Documents → Academy
Ticket → EfestoDevExtension
```

La piattaforma deve essere in grado di esistere senza conoscere i verticali.

---

# 45. Regola decisionale per ogni nuova feature

Prima di implementare una nuova funzionalità bisogna chiedersi:

> Questa funzionalità descrive Mixtum, una capability riutilizzabile, un prodotto oppure questo specifico cliente?

## Se descrive Mixtum

Va in:

```text
Core
```

## Se è una capability condivisa

Va in:

```text
Platform
```

## Se è parte di un verticale

Va in:

```text
Plugin
```

## Se è cliente/progetto specifica

Va in:

```text
Extension
```

---

# 46. Piano di migrazione di massima

La ristrutturazione non dovrebbe essere effettuata riscrivendo tutto da zero.

Conviene procedere per fasi.

---

# Fase 0 — Architectural freeze

Prima di aggiungere nuove grandi funzionalità:

- evitare nuove duplicazioni;
- evitare nuovi agent runtime;
- evitare nuove dipendenze incrociate;
- documentare l'architettura attuale;
- identificare ciò che è:
  - Core;
  - Platform;
  - Plugin;
  - Extension.

Deliverable:

```text
ARCHITECTURE.md
COMPONENTS.md
DEPENDENCIES.md
```

---

# Fase 1 — Definizione del Core

Formalizzare:

- Workspace;
- plugin registry;
- configuration;
- branding;
- event bus;
- audit;
- feature flags;
- identity integration;
- authorization primitives.

Obiettivo:

> rendere il Core indipendente dai verticali.

---

# Fase 2 — Keycloak

Centralizzare:

- login;
- logout;
- refresh token;
- SSO;
- ruoli;
- gruppi;
- sessioni;
- MFA;
- federation.

Integrare:

- Django;
- Console;
- Public Frontend.

Definire chiaramente:

```text
Keycloak identity
vs
Mixtum domain authorization
```

---

# Fase 3 — Workspace

Rendere tutte le risorse importanti workspace-aware.

Definire:

```text
Workspace
WorkspaceMembership
WorkspaceRole
WorkspaceConfiguration
WorkspacePlugin
WorkspaceBranding
```

Stabilire se un plugin può essere:

- globalmente installato;
- abilitato per specifico workspace.

---

# Fase 4 — Plugin Registry

Implementare un registry standard per:

- backend modules;
- routes;
- menu;
- permissions;
- events;
- settings;
- migrations;
- capability requirements.

Definire manifest plugin.

---

# Fase 5 — AI Runtime

È una delle fasi prioritarie.

Estrarre e consolidare:

- agent runtime;
- tool registry;
- provider abstraction;
- prompts;
- structured output;
- RAG;
- vector store abstraction;
- embeddings;
- tracing;
- observability;
- usage accounting.

Migrare progressivamente gli agenti esistenti su questo runtime.

Obiettivo:

> nessun verticale deve implementare un proprio motore AI indipendente.

---

# Fase 6 — Infrastructure Capability Layer

Formalizzare le interfacce:

```text
LLMProvider
VectorStore
ObjectStorage
Cache
TaskQueue
SearchEngine
```

Implementazioni:

```text
Regolo
OpenAI
vLLM
Ollama
Qdrant
pgvector
S3
MinIO
Redis
```

---

# Fase 7 — mixtum.yaml

Creare un manifest della distribuzione.

Deve definire:

- platform version;
- plugin;
- extension;
- provider;
- capability;
- servizi infrastrutturali;
- feature flag;
- branding;
- deployment options.

---

# Fase 8 — Docker / Kubernetes dependency resolution

Il deployment engine deve determinare i servizi necessari.

Esempio:

```text
Academy + Regolo
→ no vLLM
```

```text
Documents + RAG + Qdrant
→ deploy Qdrant
```

```text
No AI
→ nessun servizio AI
```

Output possibili:

- Docker Compose;
- Helm;
- Kubernetes manifests.

---

# Fase 9 — Console plugin architecture

Creare:

- navigation registry;
- route registry;
- permission-aware UI;
- lazy loading;
- dashboard widget registry;
- settings registry.

Mantenere inizialmente composizione a build time.

---

# Fase 10 — Separazione Public Frontend

Formalizzare:

```text
Mixtum API contract
```

Creare eventualmente:

```text
@mixtum/sdk
```

Il frontend pubblico deve poter essere sviluppato indipendentemente.

---

# Fase 11 — Migrazione Ticket

Separare:

```text
Mixtum Ticket
```

da:

```text
EfestoDev Ticket Extensions
```

Portare nel plugin generico solo ciò che è realmente ticketing.

Spostare in extension:

- finance custom;
- project linkage custom;
- subscriptions;
- repository metadata;
- workflow interni.

---

# Fase 12 — Migrazione Documents

Migrare Documents verso:

- AI Runtime unico;
- VectorStore abstraction;
- provider abstraction;
- workspace;
- plugin manifest;
- permission standard.

---

# Fase 13 — Academy

Terminare Academy solo dopo aver stabilizzato:

- Core;
- workspace;
- plugin system;
- AI Runtime.

Così il completamento del prodotto avverrà già sulla nuova architettura.

---

# Fase 14 — Events

Applicare lo stesso principio.

Events deve usare:

- payments condivisi;
- workspace;
- notifications;
- identity;
- plugin runtime.

Non deve reimplementare capability esistenti.

---

# Fase 15 — Hardening

Dopo la migrazione:

- dependency checks;
- compatibility matrix;
- plugin version constraints;
- test automatici;
- API contracts;
- migration strategy;
- rollback;
- observability;
- audit.

---

# 47. Priorità consigliate

Ordine di priorità:

```text
1. Boundaries architetturali
2. Keycloak
3. Workspace
4. Plugin registry
5. AI Runtime
6. Infrastructure abstractions
7. mixtum.yaml
8. Docker/K8S composition
9. Console plugin composition
10. Migrazione Ticket
11. Migrazione Documents
12. Completamento Academy
13. Completamento Events
```

Motivazione:

Con i moderni coding agent è relativamente semplice completare rapidamente nuove feature.

È molto più costoso sistemare in seguito:

- fork;
- duplicazioni;
- coupling;
- incompatibilità;
- migrazioni divergenti.

Conviene quindi consolidare prima l'architettura.

---

# 48. Roadmap possibile

## Milestone 1 — Platform Foundation

Obiettivo:

```text
Mixtum Core stabile
```

Include:

- Keycloak;
- Workspace;
- Branding;
- Config;
- Plugin Registry;
- Event Bus.

---

## Milestone 2 — AI Foundation

Obiettivo:

```text
Unico AI Runtime
```

Include:

- provider;
- agents;
- tools;
- RAG;
- Qdrant abstraction;
- tracing;
- observability.

---

## Milestone 3 — Deployment Foundation

Obiettivo:

```text
Mixtum distribution = declarative configuration
```

Include:

- mixtum.yaml;
- Docker;
- K8S;
- dependency graph;
- optional infrastructure.

---

## Milestone 4 — Productization

Portare:

```text
Ticket
Documents
Academy
Events
```

sul modello plugin.

---

## Milestone 5 — Extension model

Formalizzare API per customizzazioni cliente.

Esempio:

```text
hooks
events
service interfaces
frontend extension points
settings
custom permissions
```

---

# 49. Esempio installazione EfestoDev target

```text
Mixtum EfestoDev
│
├── Core
│
├── Platform
│   ├── AI
│   ├── RAG
│   ├── Payments
│   └── Notifications
│
├── Plugins
│   ├── Ticket
│   ├── Documents
│   └── Project Manager
│
└── Extensions
    └── EfestoDev
        ├── TicketProjectIntegration
        ├── TicketFinance
        ├── SubscriptionIntegration
        └── RepositoryInfo
```

---

# 50. Esempio cliente con Ticket + Academy

```text
Mixtum Cliente X
│
├── Core
│
├── Ticket
├── Academy
├── AI Runtime
└── custom_cliente_x
```

Stessa istanza.

Stesso:

- Keycloak;
- workspace;
- database;
- Console;
- branding;
- AI Runtime.

I due plugin possono interagire attraverso eventi.

---

# 51. Esempio cliente senza AI locale

```yaml
plugins:
  - ticket
  - academy

ai:
  enabled: true
  provider: regolo

rag:
  enabled: false
```

Deployment:

```text
Django
Celery
Redis
Postgres
Keycloak
Console
Public Frontend
```

Niente:

```text
Qdrant
vLLM
```

---

# 52. Esempio cliente con AI locale e RAG

```yaml
plugins:
  - documents
  - academy

ai:
  enabled: true
  provider: vllm

rag:
  enabled: true
  backend: qdrant
```

Deployment:

```text
Django
Celery
Redis
Postgres
Keycloak
Console
Public Frontend
Qdrant
vLLM
```

---

# 53. Principi architetturali finali

## Principio 1

Mixtum Core deve essere piccolo.

## Principio 2

I verticali sono plugin.

## Principio 3

Le customizzazioni sono extension.

## Principio 4

I plugin non devono essere forkati per cliente.

## Principio 5

Gli AI Agent condividono un unico runtime.

## Principio 6

Qdrant e vLLM sono infrastruttura, non logica applicativa.

## Principio 7

Keycloak è il centro dell'identità.

## Principio 8

Le autorizzazioni di dominio possono restare in Mixtum.

## Principio 9

La Console è unica.

## Principio 10

Il Public Frontend è indipendente e customizzabile.

## Principio 11

Ticket, Documents, Academy ed Events devono poter coesistere nella stessa istanza.

## Principio 12

Le interazioni tra plugin devono avvenire tramite boundary espliciti.

## Principio 13

Prima modularizzare, poi eventualmente distribuire.

## Principio 14

Il deployment deve essere dichiarativo.

## Principio 15

L'infrastruttura deve essere attivata solo quando richiesta.

---

# 54. Visione finale

Mixtum dovrebbe arrivare a funzionare in questo modo:

```text
                 Mixtum Platform
                        │
        ┌───────────────┼────────────────┐
        │               │                │
      Ticket         Documents        Academy
        │               │                │
        └───────────────┼────────────────┘
                        │
                     Events
                        │
                        ▼
               Project Extensions
                        │
                        ▼
                    Deployment
                        │
          ┌─────────────┴─────────────┐
          │                           │
       Docker                      Kubernetes
```

La singola distribuzione viene descritta da:

```text
configuration
+
plugins
+
capabilities
+
extensions
+
branding
+
public frontend
```

Questo consente di avere un framework:

- aggiornabile;
- riusabile;
- multi-prodotto;
- multi-tenant;
- AI-native;
- cloud-ready;
- deployabile on-premise;
- adatto a SaaS;
- adatto a installazioni dedicate;
- personalizzabile senza fork.

---

# 55. Criterio pratico da usare durante lo sviluppo

Per ogni nuova feature:

> "Questa funzionalità appartiene alla piattaforma, a una capability trasversale, a un prodotto oppure a questa specifica installazione?"

La risposta deve determinare direttamente dove viene scritto il codice.

Questa semplice regola dovrebbe diventare uno dei vincoli principali di sviluppo di Mixtum.


---

# Invarianti per lo sviluppo assistito

## Dependency rule

    Extension -> Plugin -> Platform -> Core

## Capability rule

Corretto:

    Documents -> VectorStore -> QdrantAdapter
    Academy   -> LLMProvider -> Regolo/VLLM/OpenAI

Da evitare:

    Documents -> QdrantClient
    Academy   -> RegoloClient

## Cross-plugin communication

Ordine di preferenza:
1. event contract;
2. capability/service interface;
3. API interna stabile;
4. import diretto di internals solo se esplicitamente autorizzato.

## Service extraction

Estrarre un servizio solo con una ragione operativa:
- scaling indipendente;
- trust/security boundary;
- lifecycle indipendente;
- carico radicalmente diverso;
- servizio condiviso da molte installazioni.

La sola separazione di dominio non basta.

## Project customization

Una customizzazione cliente va in Extension.
Se diventa genericamente utile, può essere promossa dopo aver rimosso i dettagli specifici.
