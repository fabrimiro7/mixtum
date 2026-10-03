# Mixtum Console

Console condivisa Mixtum, basata su Angular 22.2.1 e CLI 22.2.0.

## Development server

Run `ng serve` for a dev server. Navigate to `http://localhost:4200/`. The application will automatically reload if you change any of the source files.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory.

## Running unit tests

Eseguire `npm test` dalla directory `console/`. Il comando compila i pacchetti Angular dei plugin, crea un workspace temporaneo con le loro versioni compilate e avvia Vitest in Chromium tramite Playwright. L'installazione normale mantiene i riferimenti ai sorgenti per il reload durante lo sviluppo; il test non modifica il lockfile della Console. Se Chromium manca, installarlo con `npx playwright install chromium`.

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via a platform of your choice. To use this command, you need to first add a package that implements end-to-end testing capabilities.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.

## Bulk emission workflow

- `POST /api/crea-fattura-proforme/` accepts an ordered array of proforma IDs, reuses the existing Mexal emission logic, and stops at the first failure so the client can surface the partial results.
- The Angular `ProformaInvoiceService.emitProformas` helper calls this endpoint, while `ProformaInvoicesListComponent` wires a selection mode with numbered checkboxes and the new “Emetti selezionate” button to control the order.
