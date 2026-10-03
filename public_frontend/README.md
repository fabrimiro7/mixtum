# AdrPaymentHub

This Public Frontend uses Angular 22.2.1 and CLI 22.2.0.

## Development server

Run `npm start` for a dev server at `http://localhost:4300/`. The application will automatically reload if you change any of the source files.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory.

## Running unit tests

Run `npm test -- --watch=false` to execute the tests with Angular's Vitest builder in Chromium headless. Install the browser once with `npx playwright install chromium` if it is not present locally.

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via a platform of your choice. To use this command, you need to first add a package that implements end-to-end testing capabilities.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.

## Bulk emission workflow

- `POST /api/crea-fattura-proforme/` accepts an ordered array of proforma IDs, reuses the existing Mexal emission logic, and stops at the first failure so the client can surface the partial results.
- The Angular `ProformaInvoiceService.emitProformas` helper calls this endpoint, while `ProformaInvoicesListComponent` wires a selection mode with numbered checkboxes and the new “Emetti selezionate” button to control the order.
