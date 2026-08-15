"""ChrisCryptSN - hardened local-first cryptography core.

Strengthened from kliewerdaniel/sovereign-sales-worker's auth/secrets modules:
Argon2id (or PBKDF2@600k) password hashing, XChaCha20-Poly1305 (or AES-GCM)
envelope encryption with per-record HKDF subkeys, and an Ed25519-signed,
tamper-evident evidence ledger. Fail-closed: refuses plaintext, never silently
weaker, and records its degradation state.
"""
from .sn import SovereignCrypto

__all__ = ["SovereignCrypto"]
__version__ = "0.1.0"
