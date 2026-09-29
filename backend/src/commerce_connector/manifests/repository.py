from dataclasses import dataclass
from pathlib import Path
from .compiler import compile_manifest
from .schema import PlatformManifest

@dataclass(slots=True)
class ManifestRecord:
    path: Path
    manifest: PlatformManifest

class ManifestRepository:
    def __init__(self, root):
        self.root = Path(root)

    def discover(self):
        records = []
        for group in ("certified","generic","generated"):
            group_dir = self.root / group
            if not group_dir.exists():
                continue
            for item in sorted(group_dir.iterdir()):
                try:
                    if item.is_dir() and (item/"manifest.yaml").exists():
                        records.append(ManifestRecord(item, compile_manifest(item)))
                    elif item.is_file() and item.suffix in {".yaml",".yml"}:
                        records.append(ManifestRecord(item, compile_manifest(item)))
                except Exception:
                    continue
        return records

    def get_by_id(self, manifest_id):
        for record in self.discover():
            if record.manifest.id == manifest_id:
                return record
        raise KeyError(f"Manifest not found: {manifest_id}")
