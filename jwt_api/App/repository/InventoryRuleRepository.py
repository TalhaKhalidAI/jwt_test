# App/repository/InventoryRuleRepository.py

from datetime import datetime, timezone
import logging
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import select, or_, and_, desc, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from App.api.databases.MigrateTable import (
    InventoryRule as InventoryRuleModel,
    CryptoKey as CryptoKeyModel,
)
from App.core.exceptions import (
    InventoryRuleNotFoundError,
    DuplicateInventoryRuleError,
    CryptoKeyNotFoundError,
    InfrastructureError,
)

logger = logging.getLogger(__name__)


class InventoryRuleRepository:
    """
    Repository for InventoryRule (JWT Claim Validation Rules) operations.

    Transaction policy:
        This repository does NOT commit. The service layer manages transactions.

    Architectural design:
        - Rules can be scoped to a specific CryptoKey or global (key_id IS NULL).
        - High read-frequency during scan evaluation; supports caching-friendly queries.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    @staticmethod
    def _parse_uuid(val: str | uuid.UUID) -> Optional[uuid.UUID]:
        """Safely parse string or UUID object to prevent asyncpg type errors."""
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except (ValueError, AttributeError):
            return None

    async def _safe_flush(self) -> None:
        """Flush pending ORM operations without committing."""
        await self.session.flush()

    # ================================================================
    # READ OPERATIONS
    # ================================================================
    async def get_by_id(
        self, rule_id: str | uuid.UUID, for_update: bool = False
    ) -> Optional[InventoryRuleModel]:
        """Fetch a single rule by its primary UUID."""
        parsed_id = self._parse_uuid(rule_id)
        if not parsed_id:
            return None

        stmt = select(InventoryRuleModel).where(InventoryRuleModel.id == parsed_id)
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, rule_name: str) -> Optional[InventoryRuleModel]:
        """Fetch a rule by its unique human-readable rule_name."""
        result = await self.session.execute(
            select(InventoryRuleModel).where(InventoryRuleModel.rule_name == rule_name)
        )
        return result.scalar_one_or_none()

    async def get_applicable_rules(
        self, key_id: Optional[str | uuid.UUID] = None
    ) -> List[InventoryRuleModel]:
        """
        Fetch active rules applicable to a verification context.
        
        Returns:
            - If key_id is provided: All active rules specific to that key_id
              PLUS all active global rules (where key_id IS NULL).
            - If key_id is None: All active global rules.
        """
        stmt = select(InventoryRuleModel).where(InventoryRuleModel.is_active == True)

        if key_id is not None:
            parsed_key_id = self._parse_uuid(key_id)
            stmt = stmt.where(
                or_(
                    InventoryRuleModel.key_id == parsed_key_id,
                    InventoryRuleModel.key_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(InventoryRuleModel.key_id.is_(None))

        stmt = stmt.order_by(desc(InventoryRuleModel.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_rules(
        self,
        key_id: Optional[str | uuid.UUID] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InventoryRuleModel]:
        """Paginated rule lookup for administrative interfaces."""
        stmt = select(InventoryRuleModel).order_by(desc(InventoryRuleModel.created_at))

        if key_id is not None:
            parsed_key_id = self._parse_uuid(key_id)
            stmt = stmt.where(InventoryRuleModel.key_id == parsed_key_id)

        if is_active is not None:
            stmt = stmt.where(InventoryRuleModel.is_active == is_active)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_rules_by_user(
        self,
        user_id: int,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InventoryRuleModel]:
        """Fetch rules associated with keys owned by a specific user."""
        stmt = (
            select(InventoryRuleModel)
            .join(CryptoKeyModel, InventoryRuleModel.key_id == CryptoKeyModel.id)
            .where(CryptoKeyModel.created_by == user_id)
            .order_by(desc(InventoryRuleModel.created_at))
        )
        if is_active is not None:
            stmt = stmt.where(InventoryRuleModel.is_active == is_active)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


    # ================================================================
    # WRITE OPERATIONS
    # ================================================================
    async def create(
        self,
        rule_name: str,
        matching_claim_key: str,
        expected_value: str,
        key_id: Optional[str | uuid.UUID] = None,
        is_active: bool = True,
    ) -> InventoryRuleModel:
        """
        Create a new inventory claim verification rule. Does NOT commit.

        Raises:
            CryptoKeyNotFoundError: If key_id references a non-existent key.
            DuplicateInventoryRuleError: If rule_name already exists.
        """
        parsed_key_id = None
        if key_id is not None:
            parsed_key_id = self._parse_uuid(key_id)
            if not parsed_key_id:
                raise CryptoKeyNotFoundError(f"Invalid key_id format: {key_id}")

        rule = InventoryRuleModel(
            rule_name=rule_name,
            matching_claim_key=matching_claim_key,
            expected_value=expected_value,
            key_id=parsed_key_id,
            is_active=is_active,
        )
        self.session.add(rule)

        try:
            await self._safe_flush()
        except IntegrityError as e:
            msg = str(e.orig).lower() if hasattr(e, "orig") and e.orig else str(e).lower()
            if "foreign key" in msg and "crypto_keys" in msg:
                raise CryptoKeyNotFoundError(
                    f"Referenced CryptoKey {key_id} does not exist"
                ) from e
            if "unique" in msg or "duplicate key" in msg:
                raise DuplicateInventoryRuleError(
                    f"An inventory rule with name '{rule_name}' already exists."
                ) from e
            raise

        await self.session.refresh(rule)
        logger.info(f"Created InventoryRule: {rule.id} ('{rule.rule_name}')")
        return rule

    async def update(
        self,
        rule_id: str | uuid.UUID,
        rule_name: Optional[str] = None,
        matching_claim_key: Optional[str] = None,
        expected_value: Optional[str] = None,
        key_id: Optional[str | uuid.UUID] = None,
        is_active: Optional[bool] = None,
    ) -> InventoryRuleModel:
        """
        Update an existing inventory rule. Does NOT commit.

        Raises:
            InventoryRuleNotFoundError: If the rule does not exist.
            CryptoKeyNotFoundError: If the updated key_id is invalid.
        """
        rule = await self.get_by_id(rule_id, for_update=True)
        if not rule:
            raise InventoryRuleNotFoundError(f"Inventory rule {rule_id} not found")

        if rule_name is not None:
            rule.rule_name = rule_name
        if matching_claim_key is not None:
            rule.matching_claim_key = matching_claim_key
        if expected_value is not None:
            rule.expected_value = expected_value
        if is_active is not None:
            rule.is_active = is_active
        if key_id is not None:
            parsed_key_id = self._parse_uuid(key_id)
            if not parsed_key_id:
                raise CryptoKeyNotFoundError(f"Invalid key_id format: {key_id}")
            rule.key_id = parsed_key_id

        try:
            await self._safe_flush()
        except IntegrityError as e:
            msg = str(e.orig).lower() if hasattr(e, "orig") and e.orig else str(e).lower()
            if "foreign key" in msg and "crypto_keys" in msg:
                raise CryptoKeyNotFoundError(
                    f"Referenced CryptoKey {key_id} does not exist"
                ) from e
            if "unique" in msg or "duplicate key" in msg:
                raise DuplicateInventoryRuleError(
                    f"An inventory rule with name '{rule_name}' already exists."
                ) from e
            raise

        logger.info(f"Updated InventoryRule: {rule.id}")
        return rule

    async def set_active_status(
        self, rule_id: str | uuid.UUID, is_active: bool
    ) -> InventoryRuleModel:
        """Enable or disable a rule without changing its definitions."""
        return await self.update(rule_id, is_active=is_active)

    async def delete(self, rule_id: str | uuid.UUID) -> bool:
        """
        Permanently remove an inventory rule. Does NOT commit.

        Raises:
            InventoryRuleNotFoundError: If the rule does not exist.
        """
        rule = await self.get_by_id(rule_id, for_update=True)
        if not rule:
            raise InventoryRuleNotFoundError(f"Inventory rule {rule_id} not found")

        await self.session.delete(rule)
        await self._safe_flush()
        logger.info(f"Deleted InventoryRule: {rule_id}")
        return True
