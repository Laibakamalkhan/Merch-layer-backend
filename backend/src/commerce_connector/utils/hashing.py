import hashlib
def sha256_hex(value: bytes):
    return hashlib.sha256(value).hexdigest()
