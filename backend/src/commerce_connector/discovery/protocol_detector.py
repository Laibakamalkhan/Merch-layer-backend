def candidate_discovery_urls(base_url):
    root=base_url.rstrip("/")
    return {
        "openapi":[f"{root}/openapi.json",f"{root}/swagger.json",f"{root}/api-docs"],
        "graphql":[f"{root}/graphql",f"{root}/api/graphql"],
        "wsdl":[f"{root}?wsdl"],
    }
