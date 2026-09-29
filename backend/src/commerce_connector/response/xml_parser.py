import xml.etree.ElementTree as ET
def _to_dict(element):
    children = list(element)
    if not children: return element.text.strip() if element.text else None
    result = {}
    for child in children:
        key = child.tag.split("}")[-1]
        value = _to_dict(child)
        if key in result:
            if not isinstance(result[key],list): result[key] = [result[key]]
            result[key].append(value)
        else: result[key] = value
    return result
def parse_xml(raw): return _to_dict(ET.fromstring(raw))
