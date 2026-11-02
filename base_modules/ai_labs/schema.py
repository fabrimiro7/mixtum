from rest_framework.exceptions import ValidationError


def validate_schema(schema, value, *, path="input"):
    """Validate the JSON-schema subset accepted by public AI contracts."""
    if not schema:
        return
    if not isinstance(schema, dict):
        raise ValidationError({path: "Schema non valido."})
    expected = schema.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    expected_types = expected if isinstance(expected, list) else [expected] if expected else []
    if any(item not in matches for item in expected_types):
        raise ValidationError({path: f"Tipo schema non supportato: {expected}."})
    if expected_types and not any(matches[item] for item in expected_types):
        raise ValidationError({path: f"Tipo atteso: {expected}."})
    effective = next((item for item in expected_types if matches[item]), None)
    if effective == "object":
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if not isinstance(required, list) or not isinstance(properties, dict):
            raise ValidationError({path: "Schema object non valido."})
        missing = [name for name in required if name not in value]
        if missing:
            raise ValidationError({path: f"Campi obbligatori mancanti: {', '.join(missing)}."})
        if schema.get("additionalProperties") is False:
            unexpected = set(value) - set(properties)
            if unexpected:
                raise ValidationError({path: f"Campi non ammessi: {', '.join(sorted(unexpected))}."})
        for name, child_schema in properties.items():
            if name in value:
                validate_schema(child_schema, value[name], path=f"{path}.{name}")
    elif effective == "array":
        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > int(max_items):
            raise ValidationError({path: "Numero massimo di elementi superato."})
        for index, item in enumerate(value):
            validate_schema(schema.get("items", {}), item, path=f"{path}[{index}]")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError({path: "Valore non ammesso."})
    if isinstance(value, str):
        if schema.get("maxLength") is not None and len(value) > int(schema["maxLength"]):
            raise ValidationError({path: "Lunghezza massima superata."})


def value_at_path(value, path):
    current = value
    if not path:
        return current
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdecimal() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise ValidationError({"path": f"Percorso non disponibile: {path}."})
    return current
