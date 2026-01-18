import secrets

secret = secrets.token_hex(32)
print(f"SECRET_KEY = \"{secret}\"")

with open("../.env", "a") as f:
    f.write(f"\nSECRET_KEY={secret}")
    
print("Key saved to .env!")
