from datetime import datetime, timezone, timedelta
import jwt
import hashlib
import secrets
import string
import pyotp
import bcrypt
from fastapi import Request
import os
import json

# Secret Key Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "DARKNIGHT_CHANDIGARH_POLICE_SECURE_JWT_SECRET_KEY_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
REAUTH_TOKEN_EXPIRE_MINUTES = 10

def hash_password(password: str) -> str:
    """Hashes password using BCrypt (rounds=12)."""
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored BCrypt hash."""
    if not plain_password or not hashed_password:
        return False
    pwd_bytes = plain_password.encode('utf-8')[:72]
    hash_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generates short-lived Access JWT token (15 mins default)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token() -> tuple[str, str]:
    """
    Generates a cryptographically random refresh token string and its SHA-256 hash.
    Returns: (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash

def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token string."""
    return hashlib.sha256(token.encode()).hexdigest()

def create_reauth_token(user_id: int) -> str:
    """Generates short-lived Re-Authentication state token (10 mins)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=REAUTH_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "reauth"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt_token(token: str) -> dict:
    """Decodes and validates JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None

# TOTP 2FA Helpers
def generate_totp_secret() -> str:
    """Generates a new TOTP secret key for 2FA."""
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    """Generates standard otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="DarKnight Chandigarh Police")

def verify_totp_code(secret: str, code: str) -> bool:
    """Verifies a 6-digit TOTP code against the secret."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip())

# One-time Recovery Codes
def generate_recovery_codes() -> tuple[list[str], str]:
    """
    Generates 8 cryptographically random recovery codes.
    Returns: (list_of_raw_codes, json_string_of_hashed_codes)
    """
    raw_codes = []
    hashed_codes = []
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(8):
        code = ''.join(secrets.choice(alphabet) for _ in range(10))
        # Format as XXXXX-XXXXX
        formatted_code = f"{code[:5]}-{code[5:]}"
        raw_codes.append(formatted_code)
        hashed_codes.append(hashlib.sha256(formatted_code.encode()).hexdigest())
    return raw_codes, json.dumps(hashed_codes)

def verify_and_consume_recovery_code(code: str, hashed_codes_json: str) -> tuple[bool, str]:
    """
    Verifies if code matches any stored recovery code hash.
    If valid, removes the consumed hash and returns (True, updated_json_string).
    """
    if not code or not hashed_codes_json:
        return False, hashed_codes_json
    try:
        hashed_list = json.loads(hashed_codes_json)
    except (json.JSONDecodeError, TypeError):
        return False, hashed_codes_json

    target_hash = hashlib.sha256(code.strip().encode()).hexdigest()
    if target_hash in hashed_list:
        hashed_list.remove(target_hash)  # Permanently invalidate single-use code
        return True, json.dumps(hashed_list)
    return False, hashed_codes_json

# Request IP Context
def get_client_ip(request: Request) -> str:
    """Extracts client IP address safely considering reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
