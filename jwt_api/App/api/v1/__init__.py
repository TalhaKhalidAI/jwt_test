from fastapi import APIRouter
from .UserAuth import router
from .Admin import admin_router
from .Users import user_router
from .MFA import mfa_router
from .EmailOTP import email_otp_router
from .CryptoKeys import crypto_keys_router
from .InventoryRules import inventory_rules_router
from .Scans import scans_router
from .Shifts import shifts_router

app_router = APIRouter()
app_router.include_router(router, prefix="/auth")
app_router.include_router(admin_router, prefix="/admin")
app_router.include_router(user_router, prefix="/users")
app_router.include_router(mfa_router, prefix="/mfa")
app_router.include_router(email_otp_router)
app_router.include_router(crypto_keys_router)
app_router.include_router(inventory_rules_router)
app_router.include_router(scans_router)
app_router.include_router(shifts_router)