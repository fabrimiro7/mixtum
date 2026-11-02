from django.db import migrations


def register_tool(apps, schema_editor):
    apps.get_model("ai_labs", "ToolDefinition").objects.update_or_create(
        workspace=None, key="ticket.list_visible",
        defaults={
            "name": "Elenca Ticket visibili",
            "description": "Restituisce soltanto i Ticket visibili all'identità che esegue il flow o agente.",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object", "required": ["tickets"]},
            "enabled": True,
        },
    )


def unregister_tool(apps, schema_editor):
    apps.get_model("ai_labs", "ToolDefinition").objects.filter(workspace=None, key="ticket.list_visible").delete()


class Migration(migrations.Migration):
    dependencies = [("ticket", "0001_initial"), ("ai_labs", "0003_remove_run_ai_run_definition_matches_kind_and_more")]
    operations = [migrations.RunPython(register_tool, unregister_tool)]
