def header(text):
    print("\n"+"="*72); print(text); print("="*72)
def show_results(results):
    for connection in results:
        print(f"\n{connection['name']} ({connection['manifest_id']})")
        for resource in connection["resources"]:
            print(f"  {resource['resource']}: {resource['records']} records, {len(resource['pages'])} pages")
