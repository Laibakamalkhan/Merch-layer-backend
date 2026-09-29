from pathlib import Path
from typing import Any
import yaml
from commerce_connector.core.exceptions import ManifestError

def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ManifestError(f"Unable to read YAML {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ManifestError(f"Manifest file must contain an object: {path}")
    return data

def load_manifest_source(path):
    source = Path(path)
    if source.is_file():
        return _load_yaml(source)
    if not source.is_dir():
        raise ManifestError(f"Manifest path does not exist: {source}")
    root_file = source / "manifest.yaml"
    if not root_file.exists():
        raise ManifestError(f"Directory manifest is missing {root_file}")
    root = _load_yaml(root_file)
    resources_value = root.get("resources", [])
    resources = {}
    if isinstance(resources_value, dict):
        resources.update(resources_value)
    elif isinstance(resources_value, list):
        for resource_name in resources_value:
            candidates = [
                source / f"{resource_name}.yaml",
                source / "resources" / f"{resource_name}.yaml",
            ]
            resource_file = next((c for c in candidates if c.exists()), None)
            if not resource_file:
                raise ManifestError(f"Resource '{resource_name}' has no YAML file in {source}")
            data = _load_yaml(resource_file)
            data.setdefault("name", str(resource_name))
            resources[str(resource_name)] = data
    root["resources"] = resources
    return root
