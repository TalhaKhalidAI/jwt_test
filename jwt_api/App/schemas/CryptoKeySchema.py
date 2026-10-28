# App/schemas/CryptoKeySchema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List,Dict,Any


class CreateKeyRequest(BaseModel):
    """Payload to request the generation of a new asymmetric RSA keypair."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable key identifier/name")
    kid: Optional[str] = Field(None, max_length=100, description="Custom Key ID (auto-generated if omitted)")
    key_size: int = Field(2048, description="RSA key size in bits (2048 or 4096)")
    target_user_id: Optional[int] = Field(
        None, 
        description="Target user ID to assign this key to (Admin-only capability. Normal users can only create for themselves)"
    )
    assigned_permissions: Optional[List[str]] = Field(
        None,
        description="Optional list of permissions to assign to the target user upon key creation (Admin-only capability)"
    )



class RotateKeyRequest(BaseModel):
    """Payload to trigger an active key rotation."""
    name: str = Field(..., min_length=1, max_length=100, description="Name for the new active keypair")
    key_size: int = Field(2048, description="RSA key size in bits (2048 or 4096)")
    target_user_id: Optional[int] = Field(None, description="Admin-only: assign new key to target user")


class RevokeKeyRequest(BaseModel):
    """Payload to revoke an active key."""
    reason: str = Field(..., min_length=3, max_length=255, description="Auditable justification for revocation")


class KeyResponse(BaseModel):
    """Safe public representation of a Cryptographic Key."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kid: str
    public_key: str
    status: str
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None


class KeyListResponse(BaseModel):
    """Paginated key listing response."""
    items: List[KeyResponse]
    limit: int
    offset: int
    total: int


class JWKItem(BaseModel):
    """Single JSON Web Key item representation."""
    kid: str
    kty: str = "RSA"
    alg: str = "RS256"
    use: str = "sig"
    public_key: str


class JWKSResponse(BaseModel):
    """JWKS standard collection of active public keys."""
    keys: List[JWKItem]


class IssueTokenRequest(BaseModel):
    """Payload to issue an RS256 token signed by an RSA key in the database."""
    target_user_id: Optional[int] = Field(
        None, 
        description="Target user ID to generate token for (Admin-only capability. Normal users generate tokens for themselves)"
    )
    key_id: Optional[str] = Field(
        None, 
        description="Optional CryptoKey UUID to sign with (Defaults automatically to the primary active key)"
    )
    expires_in_minutes: int = Field(
        60, 
        ge=1, 
        le=43200, 
        description="Token expiration duration in minutes (1 min to 30 days)"
    )
    assigned_permissions: Optional[List[str]] = Field(
        None,
        description="Optional list of permissions to grant/assign to this user in DB and embed in the token (Admin-only capability)"
    )
    extra_claims: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional additional custom claims to embed into the JWT payload"
    )


class IssueTokenResponse(BaseModel):
    """Response returned upon issuing an RS256 token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    kid: str
    key_id: str
    user_id: int


class VerifyTokenRequest(BaseModel):
    """Payload to verify and decode an RS256 token against database public keys."""
    token: str = Field(..., description="RS256 signed JWT string")


class VerifyTokenResponse(BaseModel):
    """Verification result with decoded JWT claims."""
    is_valid: bool
    kid: str
    key_name: str
    payload: Dict[str, Any]

