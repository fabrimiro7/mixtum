# Mixtum Example Plugin (backend)

This is the Django half of the example plugin. Its import path and Django app
label remain `plugins.plugin_example` so existing migrations and tables are
preserved. Install it into an instance that supplies Mixtum's workspace and
identity applications. The Angular package lives in `console/` and is built
separately.

Build a wheel from this directory with `python -m pip wheel --no-deps .`.
The wheel contains Python code and migrations only; disabling the plugin in an
instance does not uninstall the distribution or delete its data.
