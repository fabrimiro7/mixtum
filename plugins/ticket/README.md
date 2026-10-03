# Ticket plugin

Minimal Mixtum Ticket proof: client companies, requesters/referents, company-scoped operator grants and workspace-scoped assistance managers. Requesters create and see their own tickets; referents and enabled operators see tickets for their companies; managers see tickets in their workspace. Assignment never grants access.

The plugin exposes `api/plugin-ticket/companies/`, `api/plugin-ticket/tickets/` and ticket detail. Company and role provisioning is superuser-only in this proof. There is no ticket mutation, SLA, attachment, notification or import of legacy data yet. Disabling the plugin removes its routes but retains its tables and records.
