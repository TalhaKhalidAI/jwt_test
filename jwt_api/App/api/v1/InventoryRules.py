# App/api/v1/InventoryRules.py
"""
Inventory Rule Management API Endpoints (Veriflow Claim Policy Engine).

Permissions & Authorization Rules:
    - Admin (role == "admin"): Can access, create, update, or delete ANY rule,
      including global rules (key_id is None).
    - Normal User with INVENTORY_RULES_*:
        * Can only access and manage rules for cryptographic keys they own.
        * Cannot create or modify global rules (403 Forbidden).
        * Cannot view or modify rules belonging to keys owned by other users (403 Forbidden).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from App.core.Connector import get_db
from App.core.LoggingInit import get_core_logger
from App.core.exceptions import (
    InventoryRuleNotFoundError,
    DuplicateInventoryRuleError,
    CryptoKeyNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from App.models.Permissions import Permission
from App.api.dependencies.permissions import require_permission
from App.services.inventory_rule_service import InventoryRuleService
from App.schemas.InventoryRuleSchema import (
    CreateInventoryRuleRequest,
    UpdateInventoryRuleRequest,
    SetRuleStatusRequest,
    InventoryRuleResponse,
    InventoryRuleListResponse,
    EvaluateClaimsRequest,
    EvaluateClaimsResponse,
)

logger = get_core_logger(__name__)
inventory_rules_router = APIRouter(prefix="/rules", tags=["Inventory Rules"])


# ============================================================================
# READ ENDPOINTS (INVENTORY_RULES_VIEW)
# ============================================================================
@inventory_rules_router.get(
    "/",
    response_model=InventoryRuleListResponse,
    summary="List inventory verification rules",
    description=(
        "Retrieve inventory rules. "
        "Admins can view all rules (global and key-specific). "
        "Normal users can only view rules associated with cryptographic keys they own."
    ),
)
async def list_rules(
    key_id: Optional[str] = Query(None, description="Filter by CryptoKey UUID (Admins only)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    return await service.list_rules(
        current_user=current_user,
        key_id=key_id,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@inventory_rules_router.get(
    "/applicable",
    summary="Get active applicable rules for verification",
    description="Fetch active rules that apply to a verification context (Global + Key-Specific).",
)
async def get_applicable_rules(
    key_id: Optional[str] = Query(None, description="Signing CryptoKey UUID"),
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    return await service.get_applicable_rules(key_id=key_id)


@inventory_rules_router.get(
    "/{rule_id}",
    response_model=InventoryRuleResponse,
    summary="Get inventory rule by ID",
    description="Fetch a specific inventory rule. Admins can access any rule; normal users only their own.",
)
async def get_rule_by_id(
    rule_id: str,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    try:
        return await service.get_rule_by_id(rule_id=rule_id, current_user=current_user)
    except InventoryRuleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# WRITE & MUTATION ENDPOINTS (CREATE, UPDATE, DELETE)
# ============================================================================
@inventory_rules_router.post(
    "/",
    response_model=InventoryRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inventory rule",
    description=(
        "Define a new claim-matching policy rule. "
        "Admins can create global rules (key_id=null) or rules for any key. "
        "Normal users can ONLY create rules for keys they own."
    ),
)
async def create_rule(
    payload: CreateInventoryRuleRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_CREATE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    try:
        return await service.create_rule(
            rule_name=payload.rule_name,
            matching_claim_key=payload.matching_claim_key,
            expected_value=payload.expected_value,
            key_id=payload.key_id,
            is_active=payload.is_active,
            current_user=current_user,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateInventoryRuleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@inventory_rules_router.put(
    "/{rule_id}",
    response_model=InventoryRuleResponse,
    summary="Update an existing inventory rule",
    description="Modify a rule. Enforces ownership: normal users can only edit rules on keys they own.",
)
async def update_rule(
    rule_id: str,
    payload: UpdateInventoryRuleRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_UPDATE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    try:
        return await service.update_rule(
            rule_id=rule_id,
            rule_name=payload.rule_name,
            matching_claim_key=payload.matching_claim_key,
            expected_value=payload.expected_value,
            key_id=payload.key_id,
            is_active=payload.is_active,
            current_user=current_user,
        )
    except InventoryRuleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateInventoryRuleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@inventory_rules_router.patch(
    "/{rule_id}/status",
    response_model=InventoryRuleResponse,
    summary="Enable or disable an inventory rule",
    description="Toggle active status of a rule enforcing ownership.",
)
async def set_rule_status(
    rule_id: str,
    payload: SetRuleStatusRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_UPDATE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    try:
        return await service.set_active_status(
            rule_id=rule_id, is_active=payload.is_active, current_user=current_user
        )
    except InventoryRuleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@inventory_rules_router.delete(
    "/{rule_id}",
    summary="Delete an inventory rule",
    description="Permanently delete an inventory rule. Enforces ownership: normal users can only delete their own rules.",
)
async def delete_rule(
    rule_id: str,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_DELETE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    try:
        await service.delete_rule(rule_id=rule_id, current_user=current_user)
        return {"status": "success", "message": f"Rule {rule_id} deleted successfully"}
    except InventoryRuleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# EVALUATION TEST BENCH
# ============================================================================
@inventory_rules_router.post(
    "/evaluate",
    response_model=EvaluateClaimsResponse,
    summary="Evaluate scanned token claims against policy rules",
    description="Tests a given set of decoded JWT claims against all applicable active inventory rules.",
)
async def evaluate_claims(
    payload: EvaluateClaimsRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.INVENTORY_RULES_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryRuleService(db)
    return await service.evaluate_claims(
        jwt_claims=payload.claims,
        key_id=payload.key_id,
    )
