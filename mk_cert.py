import json
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# 1. Generate a BRAND NEW key pair from scratch
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# 2. Extract the Private Key PEM
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode('utf-8')

# 3. Extract the Public Key PEM
public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode('utf-8')

# 4. Create the Payload
payload = {
    "user_id": 42,
    "role": "admin",
    "warehouse_id": "WH-01"
}

# 5. Sign the JWT using the Private Key
token = jwt.encode(payload, private_pem, algorithm="RS256")

# 6. Print everything you need
print("==================================================")
print("1. COPY THIS PUBLIC KEY TO YOUR APP:")
print("==================================================")
print(public_pem)

print("\n==================================================")
print("2. COPY THIS JWT TO A QR CODE GENERATOR:")
print("==================================================")
print(token)

print("\n==================================================")
print("3. VERIFY IT RIGHT NOW IN PYTHON:")
print("==================================================")
try:
    decoded = jwt.decode(token, public_pem, algorithms=["RS256"])
    print("✅ VERIFIED! Payload:", json.dumps(decoded, indent=2))
except Exception as e:
    print("❌ FAILED:", e)