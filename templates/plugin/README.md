# Starter plugin

Questo repository contiene normali pacchetti Django e Angular. Il codice generato è
un esempio funzionante da adattare al dominio reale, non un runtime proprietario.

Backend: `python -m pip wheel --no-deps --wheel-dir /percorso/wheelhouse ./backend`.
L'app Django è `mixtum_starter_plugin`, il manifest è
`mixtum_starter_plugin.manifest`. Dopo aver aggiunto il wheel e il manifest
all'istanza, eseguire `manage.py check`, `makemigrations --check --dry-run` e
`migrate` sul database previsto. Non applicare migration a un'istanza con dati
senza una procedura di backup/recovery.

Frontend: il pacchetto `mixtum-plugin-starter-plugin-console` usa solo
`@mixtum/console-api`. Finché il contratto `0.1.0` non è pubblicato, costruisci
il pacchetto `packages/console-api/dist` dal checkout Mixtum coordinato e crea
il tarball con `npm pack packages/console-api/dist --pack-destination /percorso`.
Poi copia il tarball in `console/vendor/` del plugin e, da `console/`, esegui
`npm install --save-dev --save-exact file:vendor/mixtum-console-api-0.1.0.tgz`.
Versiona il tarball, `package.json` e `package-lock.json`; esegui `npm ci` e
`npx ng-packagr -p ng-package.json -c tsconfig.lib.json`, quindi
`npm pack ./dist`. Questi sono normali comandi npm/Angular, non un runtime Mixtum.
Nell'istanza usa `make plugin-register PLUGIN_SOURCE=/percorso/a/questo-plugin`
per aggiungere i normali requisiti e punti di composizione, poi
`make console-add-package` con il tarball compilato. Revisiona i file generati
e verifica l'istanza: la registrazione non installa pacchetti né applica migration.
Il backend impone i permessi: il menu
frontend non è un controllo di sicurezza.

Per il reload locale, dopo la registrazione nell'istanza, esegui da lì
`make console-dev PLUGIN_SOURCE=/percorso/a/questo-plugin/console`. Il server
Angular usa il sorgente di questo checkout tramite un collegamento npm e
ricompila le modifiche senza una nuova installazione a ogni salvataggio. È un
percorso di sviluppo, distinto dalla build di release da tarball.

Il generatore non modifica né avvia l'istanza. Cambiare ID dopo aver applicato
la migration equivale a cambiare app label Django e richiede una migrazione dati
dedicata; non rinominare semplicemente la cartella.
