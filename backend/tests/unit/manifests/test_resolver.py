from commerce_connector.manifests.resolver import apply_connection_inputs
def test_inputs_do_not_mutate_template():
    template={"base_url":"","connection_fields":[{"key":"store_url","target":"base_url","type":"url"}]}
    runtime=apply_connection_inputs(template,{"store_url":"https://example.com"})
    assert runtime["base_url"]=="https://example.com"
    assert template["base_url"]==""
