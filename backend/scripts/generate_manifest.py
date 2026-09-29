from pathlib import Path
import shutil,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    if len(sys.argv)!=3:
        print("Usage: python scripts/generate_manifest.py <rest|graphql|soap|bulk|file_feed> <name>")
        raise SystemExit(2)
    kind,name=sys.argv[1],sys.argv[2]
    source=ROOT/"manifests"/"generic"/f"{kind}.yaml"
    destination=ROOT/"manifests"/"generated"/f"{name}.yaml"
    shutil.copyfile(source,destination); print(destination)
if __name__=="__main__":main()
