# Links: passaggio a plugin workspace-scoped

`base_modules.links` era un'app installata dal Core. La vecchia API leggeva tutti i
record e consentiva agli utenti staff di modificarli senza verificare workspace o
oggetto di destinazione. Il codice ora vive in `plugins.links`; l'app label Django
resta `links`, la tabella resta `links_link` e la migration `0001_initial` conserva
le sue operazioni. La nuova API è `/api/plugin-links/links/`. La route globale
`/api/links/links/` non è mantenuta come alias: ripubblicarla riaprirebbe
l'accesso non filtrato. I consumer della vecchia route vanno aggiornati.

La migration `links.0002` aggiunge `workspace_id` nullable e rende opzionali i
vecchi campi di destinazione generica. I record preesistenti restano con
`workspace_id = NULL`: non sono cancellati, ma non appaiono nella nuova API.
Non inferiamo il workspace dal `content_object`, che può appartenere a modelli
arbitrari o non esistere più. Una futura importazione richiede una mappatura
esplicita, revisionata e testata su una copia dei dati. L'admin del plugin è
soltanto consultabile dai superuser per permettere tale inventario, non crea o
modifica record non assegnati.

L'API impone autenticazione, appartenenza al workspace selezionato e filtro
server-side della queryset prima di lookup, update e delete. Creazione e
serializer non accettano `workspace`, `content_type` o `object_id` dal client;
il backend assegna il workspace autorizzato. La Console offre soltanto elenco e
creazione. Non effettua fetch server-side degli URL: il rischio SSRF non viene
introdotto da questa feature. URL non validi sono respinti dalla validazione
DRF; i link nel browser usano `rel="noopener noreferrer"`.

## Deploy e recovery

1. Inventariare `links_link` e fare un backup verificato prima del rilascio.
2. Distribuire backend e selezione del plugin `links` insieme; eseguire una sola
   volta le migration con il job/processo dedicato, poi avviare il web.
3. Distribuire la Console che registra `@mixtum/plugin-links-console` e aggiornare
   i consumer della vecchia URL.
4. Verificare con due workspace che vecchi record senza scope siano invisibili,
   e che nuove creazioni siano attribuite al workspace scelto.

La migration è additiva e non esegue backfill o cancellazioni. Su PostgreSQL
`ADD COLUMN` nullable e `DROP NOT NULL` non richiedono la riscrittura dei dati,
ma la creazione/verifica della FK e gli `ALTER TABLE` richiedono lock: misurare
dimensione e attività di `links_link` e provare il rilascio in staging prima di
produzione. Il test automatico SQLite verifica il passaggio da `links.0001` a
`links.0002` con un dato storico; la prova PostgreSQL resta da eseguire.

**Non fare rollback al vecchio codice dopo aver creato link workspace-only.**
La vecchia API non applica lo scope e potrebbe esporre i nuovi record. In caso
di problemi, interrompere l'esposizione della route e preferire una correzione
in avanti; un ripristino completo richiede il backup e una decisione esplicita
sui dati creati dopo il rilascio. Nessuna migration inversa viene eseguita
automaticamente quando il plugin viene disabilitato.
