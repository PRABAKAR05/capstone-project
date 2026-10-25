import os
import time
import logging
from typing import List, Optional
from uuid import UUID
import jwt
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from app.core.config import settings

logger = logging.getLogger("carebridge.security")
security_scheme = HTTPBearer(auto_error=False)

ALLOWED_ALGORITHMS = ["HS256", "RS256", "ES256"]

class SecurityContext(BaseModel):
    user_id: UUID
    hospital_id: UUID
    role: str
    email: str
    is_active: bool

def get_jwt_secret() -> str:
    # Use SUPABASE_SERVICE_ROLE_KEY or explicit JWT secret
    return os.getenv("SUPABASE_JWT_SECRET", settings.SUPABASE_SERVICE_ROLE_KEY)

def verify_jwt_token(token: str) -> dict:
    """
    Cryptographic JWT verification pipeline.
    Validates algorithm whitelist, signature, issuer, audience, and expiry.
    """
    try:
        # 1. Inspect unverified header for algorithm check
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        if not alg or alg not in ALLOWED_ALGORITHMS or alg == "none":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or prohibited token algorithm: {alg}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Decode and verify signature
        secret = get_jwt_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=[alg],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "require": ["exp", "sub", "aud"],
            },
            audience="authenticated",
            leeway=30,
        )

        # 3. Verify issuer
        expected_iss = f"{settings.SUPABASE_URL}/auth/v1"
        token_iss = payload.get("iss")
        if token_iss and token_iss != expected_iss and settings.ENVIRONMENT == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

import time
from typing import Dict, Tuple

# In-memory TTL cache for profile lookups (user_uuid -> (hospital_id, role, email, is_active, timestamp))
_PROFILE_CACHE: Dict[str, Tuple[UUID, str, str, bool, float]] = {}
_PROFILE_CACHE_TTL_SECONDS = 300.0  # 5 minutes TTL

def get_security_context(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> SecurityContext:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_jwt_token(credentials.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing subject in token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid UUID format in token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Check in-memory cache first to avoid remote DB hop
    now = time.time()
    cache_entry = _PROFILE_CACHE.get(user_id_str)
    if cache_entry and (now - cache_entry[4]) < _PROFILE_CACHE_TTL_SECONDS:
        hospital_id, role, email, is_active, _ = cache_entry
        return SecurityContext(
            user_id=user_uuid,
            hospital_id=hospital_id,
            role=role,
            email=email,
            is_active=is_active,
        )

    # 2. Fast-path: Check if valid user_metadata exists in verified token claims
    user_metadata = payload.get("user_metadata") or {}
    meta_hospital_id = user_metadata.get("hospital_id")
    meta_role = user_metadata.get("role")
    meta_email = payload.get("email") or ""
    if meta_hospital_id and meta_role:
        try:
            h_uuid = UUID(meta_hospital_id)
            if meta_role in ("receptionist", "caregiver"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ROLE_RETIRED: Role has been retired and is no longer authorized",
                )
            if meta_role in ("hospital_admin", "doctor", "nurse", "lab_technician", "patient"):
                _PROFILE_CACHE[user_id_str] = (h_uuid, meta_role, meta_email, True, now)
                return SecurityContext(
                    user_id=user_uuid,
                    hospital_id=h_uuid,
                    role=meta_role,
                    email=meta_email,
                    is_active=True,
                )
        except (ValueError, TypeError):
            pass

    # 3. Resolve profile in database using connection pool (no raw TCP connect)
    from app.core.database import get_db
    with get_db(None) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT hospital_id, role, email, is_active
                FROM public.profiles
                WHERE id = %s;
            """, (str(user_uuid),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User profile not registered in hospital",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            hospital_id, role, email, is_active = row

            if role in ("receptionist", "caregiver"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ROLE_RETIRED: Role has been retired and is no longer authorized",
                )

            if role not in ("hospital_admin", "doctor", "nurse", "lab_technician", "patient"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"ROLE_INVALID: Role '{role}' is not a recognized canonical role",
                )

            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ACCOUNT_DEACTIVATED: User account is inactive",
                )

            _PROFILE_CACHE[user_id_str] = (hospital_id, role, email, is_active, now)

            return SecurityContext(
                user_id=user_uuid,
                hospital_id=hospital_id,
                role=role,
                email=email,
                is_active=is_active,
            )

def require_role(allowed_roles: List[str]):
    def role_dependency(context: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if context.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{context.role}'",
            )
        return context
    return role_dependency
