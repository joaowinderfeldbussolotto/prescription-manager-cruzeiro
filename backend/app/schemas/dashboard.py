"""Schema do dashboard leve (3 cards)."""
from __future__ import annotations

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_clientes: int
    receitas_no_mes: int
    receitas_vencendo_30_dias: int
