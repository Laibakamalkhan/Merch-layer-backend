async def execute_resource(connector, resource, *, resume_state=None):
    pages=[]; total_records=0
    async for page in connector.stream(resource,resume_state=resume_state):
        pages.append(page)
        if page.record_count is not None: total_records += page.record_count
    return {"resource":resource,"pages":pages,"records":total_records}
