from base_modules.ai_labs.registry import ToolContract, register_tool

from .services import visible_tickets


def list_visible_tickets(*, actor, workspace, input_data, run):
    queryset = visible_tickets(user=actor, workspace=workspace)
    if input_data.get("status"):
        queryset = queryset.filter(status=input_data["status"])
    limit = min(max(int(input_data.get("limit", 20)), 1), 100)
    return {"tickets": [
        {
            "id": ticket.pk, "title": ticket.title, "description": ticket.description,
            "status": ticket.status, "company": ticket.company.name,
        }
        for ticket in queryset.select_related("company")[:limit]
    ]}


register_tool(ToolContract(
    key="ticket.list_visible", handler=list_visible_tickets,
    input_schema={
        "type": "object", "properties": {
            "status": {"type": "string", "maxLength": 32},
            "limit": {"type": "integer"},
        }, "additionalProperties": False,
    },
    output_schema={"type": "object", "required": ["tickets"], "properties": {"tickets": {"type": "array"}}},
))
