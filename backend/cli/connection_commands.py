import getpass
from commerce_connector.connection.models import Connection
from commerce_connector.connection.validator import validate_connection_inputs

def prompt_connection(record):
    manifest=record.manifest; inputs={}
    print(f"\nConfigure {manifest.name}")
    for field in manifest.connection_fields:
        prompt=field.label + (f" ({field.placeholder})" if field.placeholder else "") + ": "
        if field.type=="choice":
            options=list((field.options or {}).keys())
            print("\nOptions: "+", ".join(options))
            value=input(prompt)
        elif field.type=="secret":
            value=getpass.getpass(prompt)
        else:
            value=input(prompt)
        if not value and field.default is not None:value=field.default
        inputs[field.key]=value
    missing=validate_connection_inputs(manifest,inputs)
    if missing: raise ValueError("Missing required values: "+", ".join(missing))
    resources=sorted(manifest.resources.keys())
    print("\nAvailable resources: "+", ".join(resources))
    selection=input("Resources [all or comma-separated names]: ").strip()
    if not selection or selection.lower()=="all":selected_resources=resources
    else:
        requested={v.strip() for v in selection.split(",")}
        selected_resources=[r for r in resources if r in requested]
    default_name=manifest.name
    name=input(f"Connection name [{default_name}]: ").strip() or default_name
    return Connection(
        name=name,manifest_id=manifest.id,manifest_path=str(record.path),
        inputs=inputs,resources=selected_resources,
    )
