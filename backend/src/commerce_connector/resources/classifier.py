from .aliases import RESOURCE_ALIASES
def classify_resource(name):
    normalized=name.lower().replace("-","_").replace(" ","_")
    for canonical,aliases in RESOURCE_ALIASES.items():
        if normalized in aliases:return canonical,1.0
        if any(alias in normalized for alias in aliases):return canonical,0.7
    return None,0.0
