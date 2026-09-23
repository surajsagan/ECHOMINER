"""Cryptographic primitives: OTP generation/verification, opaque tokens, device validators."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def generate_otp(length: int = 6) -> str:
    """Uniform over the full range; leading zeros preserved."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_otp(code: str, pepper: str) -> bytes:
    """Peppered BLAKE2b. OTPs are short-lived, single-use and attempt-capped, so a
    fast keyed hash is appropriate here; passwords use Argon2id instead."""
    return hashlib.blake2b(code.encode(), key=pepper.encode()[:64], digest_size=32).digest()


def verify_otp(code: str, expected: bytes, pepper: str) -> bool:
    return hmac.compare_digest(hash_otp(code, pepper), expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def new_device_pair() -> tuple[str, str]:
    """Selector/validator split: only the selector is indexed, the validator is hashed."""
    return secrets.token_urlsafe(16), secrets.token_urlsafe(32)


def expires_in(seconds: int) -> datetime:
    return now() + timedelta(seconds=seconds)


# ---------------------------------------------------------------- admin auth --
# Password hashing uses scrypt from the standard library rather than Argon2id.
# The architecture document specified Argon2id; scrypt is chosen here because it
# is memory-hard, in the stdlib, and needs no C build stage in the ARM runtime
# image. Parameters cost ~32 MB per verification; maxmem must be raised
# explicitly because OpenSSL caps scrypt at 32 MB by default.
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 96 * 1024 * 1024


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R,
                             p=_SCRYPT_P, dklen=32, maxmem=_SCRYPT_MAXMEM)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                 n=int(n), r=int(r), p=int(p), dklen=32,
                                 maxmem=_SCRYPT_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, bytes.fromhex(digest_hex))


# ------------------------------------------------------------------- TOTP --
# RFC 6238, SHA-1, 6 digits, 30-second step. Implemented directly to avoid a
# dependency for ~20 lines of well-specified arithmetic.
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def new_totp_secret(length: int = 20) -> str:
    raw = secrets.token_bytes(length)
    bits = "".join(f"{byte:08b}" for byte in raw)
    padded = bits + "0" * (-len(bits) % 5)
    return "".join(_B32[int(padded[i:i + 5], 2)] for i in range(0, len(padded), 5))


def _b32_decode(secret: str) -> bytes:
    bits = "".join(f"{_B32.index(char):05b}" for char in secret.upper() if char in _B32)
    usable = len(bits) - (len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, usable, 8))


def totp_at(secret: str, counter: int, digits: int = 6) -> str:
    key = _b32_decode(secret)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, at: datetime | None = None, drift: int = 1) -> bool:
    """One step of drift either way absorbs ordinary clock skew."""
    if not code or not code.isdigit():
        return False
    counter = int((at or now()).timestamp() // 30)
    return any(hmac.compare_digest(totp_at(secret, counter + offset), code)
               for offset in range(-drift, drift + 1))
