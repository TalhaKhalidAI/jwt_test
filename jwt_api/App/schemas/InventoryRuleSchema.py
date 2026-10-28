# App/schemas/InventoryRuleSchema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any


class CreateInventoryRuleRequest(BaseModel):
    """Payload to create an inventory claim verification rule."""
    rule_name: str = Field(..., min_length=1, max_length=100, description="Unique name for the rule")
    matching_claim_key: str = Field(..., min_length=1, max_length=100, description="JWT claim key to inspect")
    expected_value: str = Field(..., min_length=1, max_length=255, description="Expected value the claim must match")
    key_id: Optional[str] = Field(
        None, 
        description="Associated CryptoKey UUID (Optional for admins = Global Rule. Required for normal users = Key they own)"
    )
    is_active: bool = Field(True, description="Whether the rule is immediately active")


class UpdateInventoryRuleRequest(BaseModel):
    """Payload to update an existing inventory rule."""
    rule_name: Optional[str] = Field(None, min_length=1, max_length=100)
    matching_claim_key: Optional[str] = Field(None, min_length=1, max_length=100)
    expected_value: Optional[str] = Field(None, min_length=1, max_length=255)
    key_id: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)


class SetRuleStatusRequest(BaseModel):
    """Payload to toggle rule status."""
    is_active: bool


class InventoryRuleResponse(BaseModel):
    """Public representation of an Inventory Rule."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    key_id: Optional[str] = None
    rule_name: str
    matching_claim_key: str
    expected_value: str
    is_active: bool
    created_at: Optional[str] = None


class InventoryRuleListResponse(BaseModel):
    """Paginated collection of inventory rules."""
    items: List[InventoryRuleResponse]
    limit: int
    offset: int
    total: int


class EvaluateClaimsRequest(BaseModel):
    """Payload to test or evaluate a claim set against active inventory rules."""
    claims: Dict[str, Any] = Field(..., description="Dictionary of claims decoded from a scanned JWT")
    key_id: Optional[str] = Field(None, description="Cryptographic key ID that signed the token")


class RuleViolationItem(BaseModel):
    rule_id: str
    rule_name: str
    reason: str


class EvaluateClaimsResponse(BaseModel):
    """Evaluation result for scanned claims against policy rules."""
    is_valid: bool
    evaluated_rules_count: int
    violations: List[RuleViolationItem]
