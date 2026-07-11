"""Dashboard leve — 3 cards (exige sessão válida)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.db.mongo import get_db
from app.db.serialization import utcnow
from app.models import receita as receita_repo
from app.schemas.dashboard import DashboardResponse

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    db = get_db()
    now = utcnow()
    return DashboardResponse(
        total_clientes=await receita_repo.count_total_clientes(db),
        receitas_no_mes=await receita_repo.count_receitas_no_mes(db, now),
        receitas_vencendo_30_dias=await receita_repo.count_vencendo_em(db, now, 30),
    )
