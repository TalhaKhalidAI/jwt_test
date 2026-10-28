# App/services/inventory_rule_service.py

from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from App.services.base import BaseService
from App.repository.InventoryRuleRepository import InventoryRuleRepository
from App.repository.CryptoKeyRepository import CryptoKeyRepository
from App.core.exceptions import (
    InventoryRuleNotFoundError,
    DuplicateInventoryRuleError,
    CryptoKeyNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)


class InventoryRuleService(BaseService):
    """
    Application business logic for Inventory Rule (JWT Claim Validation) operations.

    Authorization Rules:
        - Admin (role == "admin"): Can access, create, update, and delete ANY rule,
          including global rules (key_id is None).
        - Normal User with permissions:
            * Can only create rules assigned to cryptographic keys they own.
            * Cannot create, modify, or delete global rules (key_id is None).
            * Can only view, update, toggle, or delete rules belonging to their own keys.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.db = db
        self.repo = InventoryRuleRepository(db)
        self.key_repo = CryptoKeyRepository(db)

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    @staticmethod
    def _is_admin(current_user: Dict[str, Any]) -> bool:
        return current_user.get("role") == "admin"

    @staticmethod
    def _get_user_id(current_user: Dict[str, Any]) -> int:
        return current_user.get("user_id") or current_user.get("id")

    async def _verify_key_ownership(
        self, key_id: Optional[str | uuid.UUID], current_user: Dict[str, Any]
    ) -> None:
        """Verify that the key exists and belongs to current_user if not admin."""
        if self._is_admin(current_user):
            return

        if key_id is None:
            raise PermissionDeniedError(
                "Only administrators are permitted to create or modify global inventory rules"
            )

        key = await self.key_repo.get_by_id(key_id)
        if not key:
            raise CryptoKeyNotFoundError(f"Referenced CryptoKey {key_id} does not exist")

        user_id = self._get_user_id(current_user)
        if key.created_by != user_id:
            logger.warning(
                f"Unauthorized rule modification: User {user_id} attempted to manage key {key_id} owned by {key.created_by}"
            )
            raise PermissionDeniedError(
                "You are only permitted to configure inventory rules for cryptographic keys you own"
            )

    async def _verify_rule_ownership(
        self, rule, current_user: Dict[str, Any]
    ) -> None:
        """Verify that the rule belongs to the current user (via its key) if not admin."""
        if self._is_admin(current_user):
            return

        if rule.key_id is None:
            raise PermissionDeniedError(
                "Global rules can only be modified or deleted by administrators"
            )

        key = await self.key_repo.get_by_id(rule.key_id)
        user_id = self._get_user_id(current_user)
        if not key or key.created_by != user_id:
            raise PermissionDeniedError(
                "You do not have permission to manage this inventory rule"
            )

    @staticmethod
    def _to_dict(rule) -> Dict[str, Any]:
        return {
            "id": str(rule.id),
            "key_id": str(rule.key_id) if rule.key_id else None,
            "rule_name": rule.rule_name,
            "matching_claim_key": rule.matching_claim_key,
            "expected_value": rule.expected_value,
            "is_active": rule.is_active,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        }

    # ================================================================
    # CRUD: CREATE
    # ================================================================
    async def create_rule(
        self,
        rule_name: str,
        matching_claim_key: str,
        expected_value: str,
        current_user: Dict[str, Any],
        key_id: Optional[str | uuid.UUID] = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new inventory claim verification rule.

        Admin: Can create global rules (key_id=None) or rules for any key.
        Normal user: Can only create rules for keys they own.
        """
        if not rule_name or not rule_name.strip():
            raise ValidationError("Rule name cannot be empty")
        if not matching_claim_key or not matching_claim_key.strip():
            raise ValidationError("Matching claim key cannot be empty")
        if not expected_value or not expected_value.strip():
            raise ValidationError("Expected value cannot be empty")

        # Enforce key ownership
        await self._verify_key_ownership(key_id, current_user)

        rule = await self.repo.create(
            rule_name=rule_name.strip(),
            matching_claim_key=matching_claim_key.strip(),
            expected_value=expected_value.strip(),
            key_id=key_id,
            is_active=is_active,
        )

        user_id = self._get_user_id(current_user)
        logger.info(
            f"Created InventoryRule '{rule.rule_name}' ({rule.id}) by user {user_id} for key {rule.key_id}"
        )
        return self._to_dict(rule)

    # ================================================================
    # CRUD: READ
    # ================================================================
    async def get_rule_by_id(
        self, rule_id: str | uuid.UUID, current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve a specific rule, verifying read ownership."""
        rule = await self.repo.get_by_id(rule_id)
        if not rule:
            raise InventoryRuleNotFoundError(f"Inventory rule {rule_id} not found")

        # Normal users can read global rules or rules for their keys
        if not self._is_admin(current_user) and rule.key_id is not None:
            key = await self.key_repo.get_by_id(rule.key_id)
            user_id = self._get_user_id(current_user)
            if not key or key.created_by != user_id:
                raise PermissionDeniedError("You do not have access to this inventory rule")

        return self._to_dict(rule)

    async def list_rules(
        self,
        current_user: Dict[str, Any],
        key_id: Optional[str | uuid.UUID] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List inventory rules.
        - Admin: Returns all rules matching query filters (global + all keys).
        - Normal User: Returns only rules attached to keys owned by this user.
        """
        if self._is_admin(current_user):
            rules = await self.repo.list_rules(
                key_id=key_id, is_active=is_active, limit=limit, offset=offset
            )
        else:
            user_id = self._get_user_id(current_user)
            rules = await self.repo.list_rules_by_user(
                user_id=user_id, is_active=is_active, limit=limit, offset=offset
            )

        return {
            "items": [self._to_dict(r) for r in rules],
            "limit": limit,
            "offset": offset,
            "total": len(rules),
        }

    async def get_applicable_rules(
        self, key_id: Optional[str | uuid.UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch active rules applicable to token verification (Global + Key-Specific).
        Used by the scan verification engine.
        """
        rules = await self.repo.get_applicable_rules(key_id=key_id)
        return [self._to_dict(r) for r in rules]

    # ================================================================
    # CRUD: UPDATE & TOGGLE
    # ================================================================
    async def update_rule(
        self,
        rule_id: str | uuid.UUID,
        current_user: Dict[str, Any],
        rule_name: Optional[str] = None,
        matching_claim_key: Optional[str] = None,
        expected_value: Optional[str] = None,
        key_id: Optional[str | uuid.UUID] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update an existing inventory rule enforcing ownership."""
        rule = await self.repo.get_by_id(rule_id)
        if not rule:
            raise InventoryRuleNotFoundError(f"Inventory rule {rule_id} not found")

        # Verify ownership of current rule
        await self._verify_rule_ownership(rule, current_user)

        # If key_id is being changed, verify ownership of the new key
        if key_id is not None:
            await self._verify_key_ownership(key_id, current_user)

        updated_rule = await self.repo.update(
            rule_id=rule_id,
            rule_name=rule_name.strip() if rule_name else None,
            matching_claim_key=matching_claim_key.strip() if matching_claim_key else None,
            expected_value=expected_value.strip() if expected_value else None,
            key_id=key_id,
            is_active=is_active,
        )

        logger.info(f"Updated InventoryRule {rule_id} by user {self._get_user_id(current_user)}")
        return self._to_dict(updated_rule)

    async def set_active_status(
        self,
        rule_id: str | uuid.UUID,
        is_active: bool,
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Enable or disable an inventory rule."""
        return await self.update_rule(
            rule_id=rule_id, is_active=is_active, current_user=current_user
        )

    # ================================================================
    # CRUD: DELETE
    # ================================================================
    async def delete_rule(
        self, rule_id: str | uuid.UUID, current_user: Dict[str, Any]
    ) -> bool:
        """Permanently delete an inventory rule enforcing ownership."""
        rule = await self.repo.get_by_id(rule_id)
        if not rule:
            raise InventoryRuleNotFoundError(f"Inventory rule {rule_id} not found")

        await self._verify_rule_ownership(rule, current_user)

        result = await self.repo.delete(rule_id)
        logger.info(f"Deleted InventoryRule {rule_id} by user {self._get_user_id(current_user)}")
        return result

    # ================================================================
    # CLAIM VERIFICATION ENGINE
    # ================================================================
    async def evaluate_claims(
        self,
        jwt_claims: Dict[str, Any],
        key_id: Optional[str | uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate token claims against all active applicable rules.
        
        Returns:
            {
                "is_valid": bool,
                "evaluated_rules_count": int,
                "violations": List[Dict[str, str]]
            }
        """
        rules = await self.repo.get_applicable_rules(key_id=key_id)
        violations = []

        for rule in rules:
            claim_val = jwt_claims.get(rule.matching_claim_key)
            if claim_val is None:
                violations.append({
                    "rule_id": str(rule.id),
                    "rule_name": rule.rule_name,
                    "reason": f"Missing required claim: '{rule.matching_claim_key}'",
                })
            elif str(claim_val) != str(rule.expected_value):
                violations.append({
                    "rule_id": str(rule.id),
                    "rule_name": rule.rule_name,
                    "reason": (
                        f"Claim mismatch for '{rule.matching_claim_key}': "
                        f"expected '{rule.expected_value}', got '{claim_val}'"
                    ),
                })

        return {
            "is_valid": len(violations) == 0,
            "evaluated_rules_count": len(rules),
            "violations": violations,
        }
