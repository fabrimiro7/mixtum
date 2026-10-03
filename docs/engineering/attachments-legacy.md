# Allegati legacy (solo `AUTH_MODE=django`)

Le route `/api/attachments/` restano escluse in modalità Keycloak. Non sono una capability workspace-scoped né la base del futuro plugin Documents.

Gli endpoint di elenco, dettaglio, modifica, eliminazione e download limitano gli oggetti all'utente autore autenticato. La creazione imposta l'autore sul server: il campo `author` inviato dal client è ignorato. Il campo `file` nelle risposte di creazione, modifica, elenco e dettaglio contiene l'URL `/api/attachments/download/<id>/`, non l'URL dello storage. Per scaricare il file, il client deve inviare la stessa autenticazione API; un link aperto dal browser senza token non è sufficiente. Il download forza `application/octet-stream` e `Content-Disposition: attachment`, con `nosniff` e `Cache-Control: private, no-store`.

Gli upload su create e update sono limitati a 20 MiB di file. Il backend risponde 400 oltre la soglia; il template Nginx HTTPS legacy consente 21 MiB di richiesta soltanto su `/api/attachments/` per l'overhead multipart, mantenendo 2 MiB per le altre route. Un proxy diverso può avere limiti più restrittivi. Il tipo dichiarato dal browser e l'estensione del nome non sono verifiche del contenuto: non considerare sicuro un file solo perché è stato accettato.

Prima di usare questo percorso con S3 o in produzione, verificare che bucket e oggetti siano privati e che eventuali URL di storage emessi in passato non continuino a concedere accesso. Servono inoltre policy sui formati, valutazione malware, test sullo storage reale e inventario dei client che usavano direttamente il vecchio URL `file`. Il modulo non va riaperto con Keycloak senza un modello di autorizzazione workspace-scoped e relativi test negativi.
