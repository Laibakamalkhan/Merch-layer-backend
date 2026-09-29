from pathlib import Path
from commerce_connector.manifests.repository import ManifestRepository

ROOT=Path(__file__).resolve().parents[1]
records=ManifestRepository(ROOT/"manifests").discover()
print(f"Valid manifests: {len(records)}")
for record in records:
    print(f"OK  {record.manifest.id:<28} {record.path}")
