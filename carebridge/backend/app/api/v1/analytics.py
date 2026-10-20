from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_security_context, SecurityContext
from app.schemas.analytics import HospitalOperationsOverview, DepartmentalLoadMetric
from app.analytics.service import get_operations_overview, get_departmental_load

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=HospitalOperationsOverview, status_code=status.HTTP_200_OK)
def get_hospital_operations_kpis(
    time_window: str = Query("today", description="'today', '7_days', '30_days'"),
    context: SecurityContext = Depends(get_security_context),
):
    """Retrieves server-side aggregated hospital operational KPIs.
    Strictly restricted to authorized administrative personnel.
    """
    return get_operations_overview(context=context, time_window=time_window)


@router.get("/departments", response_model=List[DepartmentalLoadMetric], status_code=status.HTTP_200_OK)
def get_departments_load_breakdown(
    context: SecurityContext = Depends(get_security_context),
):
    """Retrieves department volume distribution and doctor load without exposing patient identities."""
    return get_departmental_load(context=context)
