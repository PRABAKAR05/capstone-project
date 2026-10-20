import time
import logging
from typing import Optional
from uuid import UUID
import jwt
import psycopg2
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, status, Depends
from app.core.config import settings
from app.core.security import get_jwt_secret, get_security_context, SecurityContext

logger = logging.getLogger("carebridge.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    role: str
    full_name: str
    email: str
    is_active: bool

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserResponse

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """
    Authenticate against database users and issue a signed HS256 JWT.
    """
    if not req.email or "@" not in req.email or not req.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid email and non-empty password required",
        )

    conn = psycopg2.connect(settings.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    u.id,
                    u.email,
                    (u.encrypted_password = extensions.crypt(%s, u.encrypted_password)) as password_valid,
                    p.hospital_id,
                    p.role,
                    p.full_name,
                    p.is_active
                FROM auth.users u
                JOIN public.profiles p ON p.id = u.id
                WHERE lower(u.email) = lower(%s);
            """, (req.password, str(req.email)))
            row = cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_id, email, password_valid, hospital_id, role, full_name, is_active = row

            if not password_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

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

            # Mint HS256 Supabase-compatible JWT
            now = int(time.time())
            expires_in = 86400
            payload = {
                "sub": str(user_id),
                "aud": "authenticated",
                "iss": f"{settings.SUPABASE_URL}/auth/v1",
                "email": email,
                "role": "authenticated",
                "app_metadata": {
                    "provider": "email",
                    "providers": ["email"]
                },
                "user_metadata": {
                    "full_name": full_name,
                    "role": role,
                    "hospital_id": str(hospital_id),
                },
                "iat": now,
                "exp": now + expires_in,
            }

            token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")

            return LoginResponse(
                access_token=token,
                token_type="bearer",
                expires_in=expires_in,
                user=UserResponse(
                    id=user_id,
                    hospital_id=hospital_id,
                    role=role,
                    full_name=full_name,
                    email=email,
                    is_active=is_active,
                )
            )
    finally:
        conn.close()

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(context: SecurityContext = Depends(get_security_context)):
    """
    Returns the authenticated user's profile details.
    """
    conn = psycopg2.connect(settings.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, role, full_name, email, is_active
                FROM public.profiles
                WHERE id = %s;
            """, (str(context.user_id),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found",
                )
            return UserResponse(
                id=row[0],
                hospital_id=row[1],
                role=row[2],
                full_name=row[3],
                email=row[4],
                is_active=row[5],
            )
    finally:
        conn.close()
