# App/core/aes_crypto.py
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from App.core.settings import settings
from App.core.exceptions import EncryptionError, DecryptionError
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)

def _get_aes_key() -> bytes:
    """
    Decodes the dedicated ENCRYPTION_KEY from settings.
    Ensures the key is exactly 32 bytes for AES-256.
    """
    try:
        key_str = settings.ENCRYPTION_KEY.get_secret_value()
        key_bytes = base64.urlsafe_b64decode(key_str)
        
        if len(key_bytes) != 32:
            raise ValueError(f"Invalid AES key length: {len(key_bytes)} bytes. Must be 32.")
            
        return key_bytes
    except Exception as e:
        logger.critical(f"CRITICAL: ENCRYPTION_KEY is invalid or missing from .env: {e}")
        raise EncryptionError("Server encryption key is invalid") from e

def encrypt_data(plain_text: str) -> str:
    if not plain_text:
        return ""

    try:
        key = _get_aes_key()
        aesgcm = AESGCM(key)
        
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")
        
    except (ValueError, TypeError) as e:
        logger.error(f"Encryption failed due to invalid input or key: {e}")
        raise EncryptionError("Invalid data or configuration for encryption") from e
    except OverflowError as e:
        logger.error(f"Encryption failed: Data too large: {e}")
        raise EncryptionError("Data payload exceeds maximum encryption size") from e
    except Exception as e:
        logger.error(f"Unexpected encryption failure: {e}")
        raise EncryptionError("Failed to encrypt sensitive data") from e

def decrypt_data(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""

    try:
        key = _get_aes_key()
        aesgcm = AESGCM(key)
        
        combined = base64.b64decode(encrypted_text.encode("utf-8"))
        
        # Defensive check: Ensure there is enough data to split
        if len(combined) < 12:
            raise ValueError("Ciphertext is too short to contain a valid nonce")
            
        nonce = combined[:12]
        ciphertext = combined[12:]
        
        plain_text_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plain_text_bytes.decode("utf-8")
        
    except InvalidTag as e:
        logger.warning("Decryption failed: Data has been tampered with (Invalid Tag)")
        raise DecryptionError("Data integrity error: Payload has been tampered with") from e
    except (ValueError, TypeError) as e:
        logger.error(f"Decryption failed due to malformed data: {e}")
        raise DecryptionError("Malformed encrypted payload or invalid key") from e
    except Exception as e:
        logger.error(f"Unexpected decryption failure: {e}")
        raise DecryptionError("Failed to decrypt sensitive data") from e

