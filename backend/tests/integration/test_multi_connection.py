from commerce_connector.connection.models import Connection
def test_two_connections_same_manifest():
    first=Connection(name="A",manifest_id="shopify-admin-graphql",manifest_path="manifests/certified/shopify",inputs={"store_url":"https://a.myshopify.com","access_token":"a"},resources=["orders"])
    second=Connection(name="B",manifest_id="shopify-admin-graphql",manifest_path="manifests/certified/shopify",inputs={"store_url":"https://b.myshopify.com","access_token":"b"},resources=["orders"])
    assert first.connection_id!=second.connection_id
    assert first.inputs["store_url"]!=second.inputs["store_url"]
