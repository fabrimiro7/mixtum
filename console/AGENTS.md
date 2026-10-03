# Mixtum Console / Angular Rules

## Ruolo
La Console è la shell amministrativa comune.
I plugin registrano route, navigation, widget, settings e action.

Niente logica cliente-specifica nel core Console.

## Plugin UI
Preferire composizione a build time e lazy loading.
Non introdurre microfrontend runtime senza ADR.

## Permission
Route guard, menu visibility e disabled controls sono UX.
Il backend mantiene l'enforcement reale.

## Keycloak
Usare il client OIDC condiviso.
Non implementare auth parallela.
Mai mettere client secret nel browser.

## State
Evitare duplicazione di stato tra component/service/store.
Ownership chiara.

## API
Usare SDK/tipi OpenAPI condivisi quando disponibili.

## UX
Gestire loading, empty, unauthorized, forbidden, network failure e validation error.

## Branding
Usare token/variabili Mixtum.
Non hardcodare branding cliente nel core.
