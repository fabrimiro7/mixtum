# Demo support extension

Instance-owned example of an Extension → Plugin dependency. It adds a workspace-scoped summary API and Console page using Ticket's public `visible_tickets` service. It does not modify Ticket models, routes or the shared Console shell, and owns no database tables.

The instance selects it separately from product plugins in `mixtum_instance/composition.json`. It requires Ticket; removing `demo_support` from `extensions` removes its API and page while leaving Ticket enabled. This is a technical customization example, not a customer-ready report or an additional generic Mixtum plugin.
