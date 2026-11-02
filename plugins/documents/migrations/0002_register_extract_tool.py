from django.db import migrations


def register_tool(apps, schema_editor):
    ToolDefinition = apps.get_model("ai_labs", "ToolDefinition")
    ToolDefinition.objects.update_or_create(
        workspace=None,
        key="documents.extract",
        defaults={
            "name": "Estrai contenuto documento",
            "description": "Estrae testo con provenienza da una versione Documents autorizzata.",
            "input_schema": {
                "type": "object", "required": ["document_version_id"],
                "properties": {"document_version_id": {"type": "integer"}},
            },
            "output_schema": {
                "type": "object", "required": ["chunks"],
                "properties": {"chunks": {"type": "array"}},
            },
            "enabled": True,
        },
    )


def unregister_tool(apps, schema_editor):
    apps.get_model("ai_labs", "ToolDefinition").objects.filter(
        workspace=None, key="documents.extract",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial"), ("ai_labs", "0002_knowledgebase_knowledgechunk_knowledgerevision_and_more")]
    operations = [migrations.RunPython(register_tool, unregister_tool)]

