from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.security import get_security_context, SecurityContext, require_role
from app.schemas.caregiver import CaregiverRequest, CaregiverVerify, CaregiverResponse

router = APIRouter(prefix="/patient-accounts", tags=["caregiver"])

@router.post("/request", response_model=CaregiverResponse, status_code=status.HTTP_410_GONE)
def request_caregiver_link(
    payload: CaregiverRequest,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    """
    Deprecated: Caregiver registration has been permanently retired in Phase 15.
    Returns HTTP 410 Gone.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint deprecated: Caregiver and proxy account requests have been retired in Phase 15.",
    )

@router.post("/{link_id}/verify", response_model=CaregiverResponse)
def verify_caregiver_link(
    link_id: UUID,
    payload: CaregiverVerify,
    request: Request,
    context: SecurityContext = Depends(require_role(["hospital_admin", "nurse"])),
):
    """
    Deprecated: Caregiver verification desk has been permanently retired in Phase 15.
    Returns HTTP 410 Gone.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint deprecated: Caregiver verification workflow has been retired in Phase 15.",
    )

@router.patch("/{link_id}/revoke", response_model=CaregiverResponse)
def revoke_caregiver_link(
    link_id: UUID,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    """
    Deprecated: Historical non-self links are permanently frozen and revoked.
    Returns HTTP 410 Gone.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Endpoint deprecated: Historical caregiver links are frozen and permanently revoked.",
    )
