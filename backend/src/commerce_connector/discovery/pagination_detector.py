from commerce_connector.utils.paths import get_path
def detect_pagination(payload):
    if not isinstance(payload,dict): return None
    for kind,key in [("next_token","next_token"),("next_token","nextToken"),("next_url","next"),("next_url","next_url")]:
        if key in payload and payload[key]:
            return {"type":kind,"path":key,"confidence":0.85}
    page_info=get_path(payload,"pageInfo")
    if isinstance(page_info,dict) and "hasNextPage" in page_info and "endCursor" in page_info:
        return {"type":"graphql_cursor","confidence":0.95}
    return None
