# App/core/rsa_generator.py

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from App.core.exceptions import EncryptionError
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)

class RSAKeyGenerator:
    """
    A simple utility class to generate RSA keypairs in RAM.
    It returns the keys as PEM strings ready for encryption and storage.
    """

    @staticmethod
    def generate(key_size: int = 2048) -> tuple[str, str]:
        """
        Generates a new RSA keypair completely in RAM.
        Returns a tuple: (private_key_pem, public_key_pem).
        Does NOT write to disk.
        """
        try:
            # 1. Generate the private key in memory
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # 2. Derive the public key from the private key
            public_key = private_key.public_key()

            # 3. Serialize Private Key to PEM string
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode("utf-8")

            # 4. Serialize Public Key to PEM string
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode("utf-8")

            return private_pem, public_pem

        except Exception as e:
            logger.error(f"Failed to generate RSA keypair: {e}")
            raise EncryptionError("Failed to generate RSA keypair in memory") from e