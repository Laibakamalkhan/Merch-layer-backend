def validate_connection_inputs(manifest, inputs):
    missing = []
    for field in manifest.connection_fields:
        if not field.required:
            continue
        value = inputs.get(field.key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field.label)
    return missing
