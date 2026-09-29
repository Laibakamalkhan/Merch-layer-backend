from pathlib import Path
from commerce_connector.connection.manager import ConnectionManager
from commerce_connector.manifests.repository import ManifestRepository
from .connection_commands import prompt_connection
from .extraction_commands import extract
from .menu import choose_index
from .output import header,show_results

ROOT=Path(__file__).resolve().parents[1]
MANIFEST_ROOT=ROOT/"manifests"

async def run():
    header("UNIVERSAL COMMERCE CONNECTOR")
    repository=ManifestRepository(MANIFEST_ROOT)
    records=repository.discover()
    if not records:
        print("No valid connector manifests found."); return
    manager=ConnectionManager()
    while True:
        idx=choose_index(
            "Choose connector definition",
            [f"{r.manifest.name} [{r.manifest.protocol.value}]" for r in records],
        )
        connection=prompt_connection(records[idx]); manager.add(connection)
        if input("\nAdd another store/platform? [y/N]: ").strip().lower() not in {"y","yes"}:break
    header("EXTRACTION PLAN")
    for connection in manager.list():
        print(f"- {connection.name}: {', '.join(connection.resources)}")
    if input("\nStart extraction? [Y/n]: ").strip().lower() in {"n","no"}:
        print("Extraction cancelled."); return
    results=await extract(manager.list())
    header("EXTRACTION RESULTS"); show_results(results)
