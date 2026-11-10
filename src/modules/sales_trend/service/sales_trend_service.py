"""
Casos de uso e orquestração de serviços para a Tendência de Vendas (P-082.1, ADR-003 DA-08).
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Union

from src.modules.sales_trend.domain.month_windows import (
    format_year_month,
    month_index,
    parse_base_month,
    previous_month,
    validate_base_month,
)
from src.modules.sales_trend.domain.pagination import paginate
from src.modules.sales_trend.domain.ranking import (
    ProductTrendRow,
    RankingResult,
    TotaisPorVisao,
    filter_and_rank_products,
)
from src.modules.sales_trend.domain.suppliers import (
    SupplierDetailResult,
    SupplierTrendRow,
    SuppliersRankingResult,
    get_supplier_detail,
    get_suppliers_trend,
)
from src.modules.sales_trend.service.sales_trend_cache import (
    SalesTrendSnapshot,
    get_cache_status,
    get_snapshot,
    peek_snapshot,
)


@dataclass(frozen=True)
class SalesTrendServiceResult:
    """Resultado bruto do serviço para posterior conversão em DTO/schema."""
    items: Sequence[Any]
    totais_por_visao: TotaisPorVisao
    total_items: int
    total_pages: int
    page: int
    limit: int
    offset: int
    snapshot: SalesTrendSnapshot
    base_month_index: int
    mes_base_parcial: bool
    agrupamento: str
    metrica: str
    sort_window: int
    sort_dir: str


def get_sales_trend(
    base_month_str: Optional[str] = None,
    metric: str = "revenue",
    group_by: str = "product",
    sort_window: int = 3,
    sort_dir: str = "desc",
    view: str = "all",
    q: Optional[str] = None,
    min_volume: float = 0.0,
    limit: int = 50,
    offset: int = 0,
) -> SalesTrendServiceResult:
    """
    Executa a consulta de tendência de vendas (por produto ou fornecedor).
    """
    snapshot = get_snapshot()

    ref_year = snapshot.reference_date.year
    ref_month = snapshot.reference_date.month
    current_month_idx = month_index(ref_year, ref_month)
    default_base_month_idx = previous_month(current_month_idx)

    # Determina e valida Mês-Base
    if base_month_str:
        base_month_idx = parse_base_month(base_month_str)
        if base_month_idx is None:
            from src.modules.sales_trend.domain.exceptions import InvalidTrendParametersError
            raise InvalidTrendParametersError(fields=("baseMonth",))
    else:
        base_month_idx = default_base_month_idx

    first_sale_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)
    min_month_idx = month_index(first_sale_date.year, first_sale_date.month)
    max_month_idx = current_month_idx

    validate_base_month(
        base_month_index=base_month_idx,
        min_month_index=min_month_idx,
        max_month_index=max_month_idx,
        last_covered_day=snapshot.last_covered_day,
    )

    mes_base_parcial = (base_month_idx == current_month_idx)

    if group_by == "supplier":
        res_suppliers = get_suppliers_trend(
            supplier_index=snapshot.supplier_index,
            catalog=snapshot.catalog,
            monthly_sales=snapshot.monthly_sales,
            base_month_index=base_month_idx,
            metric=metric,
            sort_window=sort_window,
            sort_dir=sort_dir,
            view=view,
            q=q,
            min_volume=min_volume,
            last_covered_day=snapshot.last_covered_day,
        )
        paginated = paginate(res_suppliers.items, limit=limit, offset=offset)
        items = list(paginated.items)
        totais_visao = res_suppliers.totais_por_visao
    else:
        res_products = filter_and_rank_products(
            catalog=snapshot.catalog,
            monthly_sales=snapshot.monthly_sales,
            base_month_index=base_month_idx,
            metric=metric,
            sort_window=sort_window,
            sort_dir=sort_dir,
            view=view,
            q=q,
            min_volume=min_volume,
            last_covered_day=snapshot.last_covered_day,
        )
        paginated = paginate(res_products.items, limit=limit, offset=offset)
        items = list(paginated.items)
        totais_visao = res_products.totais_por_visao

    return SalesTrendServiceResult(
        items=items,
        totais_por_visao=totais_visao,
        total_items=paginated.total_items,
        total_pages=paginated.total_pages,
        page=paginated.page,
        limit=paginated.limit,
        offset=paginated.offset,
        snapshot=snapshot,
        base_month_index=base_month_idx,
        mes_base_parcial=mes_base_parcial,
        agrupamento=group_by,
        metrica=metric,
        sort_window=sort_window,
        sort_dir=sort_dir,
    )


def get_supplier_products(
    supplier_key: str,
    base_month_str: Optional[str] = None,
    metric: str = "revenue",
    sort_by: str = "contribution",
    sort_dir: str = "desc",
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort_window: int = 1,
) -> Tuple[SupplierDetailResult, SalesTrendSnapshot, int]:
    """
    Retorna a lista paginada de produtos de um fornecedor específico.
    """
    snapshot = get_snapshot()

    ref_year = snapshot.reference_date.year
    ref_month = snapshot.reference_date.month
    current_month_idx = month_index(ref_year, ref_month)
    default_base_month_idx = previous_month(current_month_idx)

    if base_month_str:
        base_month_idx = parse_base_month(base_month_str)
        if base_month_idx is None:
            from src.modules.sales_trend.domain.exceptions import InvalidTrendParametersError
            raise InvalidTrendParametersError(fields=("baseMonth",))
    else:
        base_month_idx = default_base_month_idx

    first_sale_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)
    min_month_idx = month_index(first_sale_date.year, first_sale_date.month)
    max_month_idx = current_month_idx

    validate_base_month(
        base_month_index=base_month_idx,
        min_month_index=min_month_idx,
        max_month_index=max_month_idx,
        last_covered_day=snapshot.last_covered_day,
    )

    detail_res = get_supplier_detail(
        supplier_key=supplier_key,
        supplier_index=snapshot.supplier_index,
        catalog=snapshot.catalog,
        monthly_sales=snapshot.monthly_sales,
        base_month_index=base_month_idx,
        metric=metric,
        sort_by=sort_by,
        sort_dir=sort_dir,
        q=q,
        limit=limit,
        offset=offset,
        last_covered_day=snapshot.last_covered_day,
        sort_window=sort_window,
    )

    return detail_res, snapshot, base_month_idx


def get_cache_state() -> Dict[str, Any]:
    """Retorna o estado do cache para o endpoint de health check."""
    snap = peek_snapshot()
    status = get_cache_status()
    if snap is None:
        return {
            "status": status,
            "dataReferencia": None,
            "ultimoDiaCoberto": None,
            "loadedAt": None,
            "counts": {},
        }
    return {
        "status": status,
        "dataReferencia": snap.reference_date.isoformat(),
        "ultimoDiaCoberto": snap.last_covered_day.isoformat(),
        "loadedAt": snap.loaded_at.isoformat(),
        "counts": snap.counts,
    }


def reload_cache() -> Dict[str, Any]:
    """Dispara recarga síncrona manual com validação de voo único e rate-limit."""
    snap = get_snapshot(force_reload=True)
    return {
        "status": "QUENTE",
        "dataReferencia": snap.reference_date.isoformat(),
        "ultimoDiaCoberto": snap.last_covered_day.isoformat(),
        "loadedAt": snap.loaded_at.isoformat(),
        "counts": snap.counts,
    }
