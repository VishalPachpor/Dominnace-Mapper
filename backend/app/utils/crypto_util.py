"""
Fernet symmetric encryption utility for broker credential storage.
ENCRYPTION_KEY must be set in environment variables.
Generate once with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet
import os


def _get_fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY is not set in environment variables.")
    return Fernet(key.encode())


def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext broker password. Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a stored broker password back to plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
