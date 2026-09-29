from commerce_connector.resources.classifier import classify_resource
def detect_resources(operations):
    output=[]
    for operation in operations:
        raw_name=operation.get("operation_id") or operation.get("name") or operation.get("path") or ""
        canonical,confidence=classify_resource(raw_name)
        if canonical:
            output.append({"canonical":canonical,"source":raw_name,"confidence":confidence})
    return output
