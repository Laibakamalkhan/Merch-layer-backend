"""Shopify credentials ko app se alag, seedha check karne ka chhota tool.

Chalane ka tareeqa (backend folder mein, .venv activate karke):
    python scripts/test_shopify_credentials.py

Yeh aap se store URL aur credentials poochhta hai (secret screen par nahi dikhta, kahin save nahi hota),
phir Shopify se seedha baat karke batata hai ke masla credentials mein hai ya app mein.
"""
import getpass
import sys
from urllib.parse import urlsplit

import httpx

API_VERSION = "2026-07"


def normalize(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    p = urlsplit(url)
    return f"https://{p.netloc}"


CHECKS = {
    "orders": "{ orders(first: 5) { nodes { id name createdAt totalPriceSet { shopMoney { amount currencyCode } } } } }",
    "products": "{ products(first: 5) { nodes { id title } } }",
    "customers": "{ customers(first: 5) { nodes { id } } }",
}


def check_resources(client, base: str, token: str) -> None:
    """Har data type ko chhota sa query bhej kar dekhta hai: kitna data aaya ya kya error aaya."""
    print("\nResource-wise check (har ek se 5 records tak mangwa kar):")
    for name, query in CHECKS.items():
        r = client.post(
            f"{base}/admin/api/{API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            json={"query": query},
        )
        try:
            body = r.json()
        except Exception:
            print(f"  {name:10s} -> HTTP {r.status_code}, jawab samajh nahi aaya")
            continue
        if body.get("errors"):
            first = body["errors"][0] if isinstance(body["errors"], list) else body["errors"]
            code = (first.get("extensions") or {}).get("code") if isinstance(first, dict) else None
            msg = first.get("message") if isinstance(first, dict) else str(first)
            print(f"  {name:10s} -> NAHI CHALA ({code or 'error'}): {str(msg)[:110]}")
        else:
            n = len((((body.get("data") or {}).get(name)) or {}).get("nodes") or [])
            note = "" if n else "  (access theek hai, lekin store mein abhi is ka data hai hi nahi)"
            print(f"  {name:10s} -> OK, {n} record(s) mile{note}")


def main() -> int:
    base = normalize(input("Store URL (jaise your-store.myshopify.com): "))
    print("\nKaun sa tareeqa? 1 = Client ID + Secret (naya, Dev Dashboard)   2 = purana shpat_ token")
    mode = input("Choose 1 ya 2: ").strip()

    with httpx.Client(timeout=30) as client:
        if mode == "2":
            token = getpass.getpass("Access token (typing nazar nahi aayegi): ").strip()
        else:
            cid = input("Client ID: ").strip()
            secret = getpass.getpass("Client Secret (typing nazar nahi aayegi): ").strip()
            r = client.post(
                f"{base}/admin/oauth/access_token",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
            )
            print(f"\n[1/2] Token exchange -> HTTP {r.status_code}")
            if r.status_code >= 400:
                print("      Shopify ka jawab:", r.text[:400])
                print("\nNatija: masla Client ID/Secret ya app install/organization mein hai (app ke code mein nahi).")
                return 1
            data = r.json()
            token = data["access_token"]
            print("      Token mil gaya. Scopes:", data.get("scope"), "| expires_in:", data.get("expires_in"))

        r = client.post(
            f"{base}/admin/api/{API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            json={"query": "{ shop { name myshopifyDomain } }"},
        )
        print(f"[2/2] Shop query -> HTTP {r.status_code}")
        print("      Jawab:", r.text[:400])
        if r.status_code == 200 and '"errors"' not in r.text:
            print("\nNatija: credentials bilkul theek hain. Ab app mein wahi values daal dein.")
            check_resources(client, base, token)
            return 0
        print("\nNatija: Shopify ne request qubool nahi ki. Upar ka jawab padhein.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
