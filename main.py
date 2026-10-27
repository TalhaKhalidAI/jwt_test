from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import uuid
# 1. Read the keys from the files you just generated
with open("veriflow-private.pem", "r") as f:
    PRIVATE_KEY = f.read()

with open("veriflow-public.pem", "r") as f:
    PUBLIC_KEY = f.read()

# 2. Define the payload (the data inside the token)
# payload = {
#     "user_id": 122,
#     "item_name": "1kg box of cpu rams",
#     "jd":"OFfline parcel transcriptor and take care of freights via veriflow app",
    
#     "exp": datetime.now(timezone.utc) + timedelta(days=12) # Expires in 12 days
# }
payload = {
    # --- 1. Standard Registered Claims (RFC 7519) ---
    "iss": "https://api.veriflow.com",                 # Issuer (Your FastAPI server)
    "sub": "user_122",                                 # Subject (The ID of the user/system)
    "aud": "veriflow-mobile-scanner",                  # Audience (Who this token is for)
    "iat": datetime.now(timezone.utc).timestamp(),     # Issued At (When it was created)
    "exp": (datetime.now(timezone.utc) + timedelta(days=12)).timestamp(), # Expiration
    "jti": str(uuid.uuid4()),                          # JWT ID (Unique ID for this specific token)

    # --- 2. Custom Business Claims ---
    "role": "warehouse_manager",                       # RBAC (Role-Based Access Control)
    "scope": "freight:read freight:scan",              # What actions this token allows
    
    # Group your freight/inventory data into a clean object
    "freight": {
        "shipment_id": "SHP-9942A",
        "sku": "CPU-RAM-1KG",
        "item_name": "1kg Box of CPU RAMs",
        "description": "Offline parcel transcription and freight management via VeriFlow.",
        "origin": "JFK-Airport",
        "destination": "LHR-Warehouse-3",
        "priority": "high"
    }
}

print("--- 1. SIGNING (Using Private Key) ---")
# 3. Encode (Sign) the JWT using the PRIVATE KEY
token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
print(f"Generated JWT:\n{token}\n")

print("--- 2. VERIFYING (Using Public Key) ---")
# 4. Decode (Verify) the JWT using the PUBLIC KEY
try:
    it=input("enter token string: ")
    decoded_payload = jwt.decode(it , PUBLIC_KEY, algorithms=["RS256"])
    print("Verification Successful! Decoded Payload:")
    print(decoded_payload)
except JWTError as e:
    print(f"Verification Failed: {e}")

print("\n--- 3. TAMPERING TEST ---")
# Let's pretend a hacker changed the payload. We will change the first letter of the token.
# (This invalidates the signature).
tampered_token = "X" + token[1:] 

try:
    # This will fail because the signature no longer matches the payload
    jwt.decode(tampered_token, PUBLIC_KEY, algorithms=["RS256"])
    print("How did this pass?!")
except JWTError as e:
    print(f"Tampered Token Rejected! Error: {e}")