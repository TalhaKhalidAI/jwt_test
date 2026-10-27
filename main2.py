from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta, timezone

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

payload = {
    "user_id": 42,
    "role": "admin",
    "exp": datetime.now(timezone.utc) + timedelta(hours=24)
}

token = jwt.encode(payload, private_pem.decode(), algorithm="RS256")

print("JWT:")
print(token)

print("PUBLIC KEY:")
print(public_pem.decode())
inp=input("Enter token string: ")
verified = jwt.decode(inp if inp else token, public_pem.decode(), algorithms=["RS256"])
print("Verified payload:", verified)