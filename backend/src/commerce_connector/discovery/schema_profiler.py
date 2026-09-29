def profile_schema(value):
    if isinstance(value,dict): return {k:profile_schema(v) for k,v in value.items()}
    if isinstance(value,list): return {"type":"array","items":profile_schema(value[0]) if value else None}
    return {"type":type(value).__name__}
