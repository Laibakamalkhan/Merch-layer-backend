from commerce_connector.utils.paths import get_path
def extract_records(response_spec, response_definition, pagination_records_path=None):
    path = response_definition.records_path or pagination_records_path
    return get_path(response_spec.data,path) if path else response_spec.data
