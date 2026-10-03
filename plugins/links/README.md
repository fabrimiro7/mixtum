# Mixtum Links (backend)

This is the Django half of the workspace-scoped Links plugin. Its Django app
label remains `links`, and its existing table and migration history remain
`links_link` / `links.0001_initial`. The Angular package lives in `console/`.

Build a wheel from this directory with `python -m pip wheel --no-deps .`.
The wheel requires a Mixtum instance that supplies workspace and identity
applications. Installing the wheel does not enable the plugin or migrate data.

Legacy generic links remain stored with `workspace_id = NULL` after the
additive migration. They are not returned by the workspace API. A trusted
operator must explicitly map or archive them before they can be exposed.
