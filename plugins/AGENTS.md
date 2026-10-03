# Mixtum Plugin Rules

## Isolation
Un plugin generico non contiene logica specifica di EfestoDev o di un cliente.
Quella logica va in Extension.

## Manifest
Ogni plugin dovrebbe dichiarare:
- name;
- version;
- core compatibility;
- required/optional capabilities;
- permissions;
- backend entrypoint;
- console extension points;
- events emitted/consumed.

## Dependencies
Limitare plugin -> plugin.
Preferire eventi o capability interface.

## Database
Ownership tabelle chiara.
Risorse tenant-specifiche workspace-scoped.

## AI
Il plugin può registrare agenti, tool, retriever e prompt.
Non crea un AI runtime parallelo.

## Infrastructure
Dichiarare capability requirement.
Non avviare direttamente container.

## Disable/remove
Disabilitare un plugin non deve avviare infrastruttura inutile.
La cancellazione dati non deve essere implicita.
