def validate_no_plaintext_secret_persistence(manifest):
    warnings=[]
    auth=manifest.get("auth",{})
    for key in ("token","password","api_key","client_secret","consumer_secret","lwa_client_secret","lwa_refresh_token"):
        value=auth.get(key)
        if value not in (None,"","RUNTIME","${RUNTIME}"):
            warnings.append(f"Static manifest contains possible plaintext secret: auth.{key}")
    return warnings
