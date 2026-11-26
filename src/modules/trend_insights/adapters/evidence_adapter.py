"""
Montagem do pacote de evidencias a partir da Tendencia (`sales_trend`) e do Indice de Afinidade (`analytics`).
Cobre celula, janelas, Base Ajustada, Grupo Afim + diagnostico de mercado (shift-share), migracao (lancamento,
canibalizacao mesmo/outro fornecedor), sazonalidade, preco, clientes perdidos, ruptura (so estoque atual),
promocao, regional por UF e leitura do residuo. Fonte ausente nunca derruba o diagnostico: a parcela vira
`NAO_AVALIADO` (P-173). Zero dado de cliente na saida; as fontes externas passam por `FactorSources`.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from src.modules.analytics.repository import sales_repository
from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from src.modules.analytics.service import product_affinity_service
from src.modules.sales_trend.domain.exceptions import BaseMonthWithoutSalesError, InvalidTrendParametersError
from src.modules.sales_trend.domain.month_windows import (
    format_year_month,
    month_index,
    parse_base_month,
    previous_month,
    validate_base_month,
)
from src.modules.sales_trend.domain.sales_trend import VALUE_SCALE, MonthlySales, SkuSeries, TrendCell, compute_cell
from src.modules.sales_trend.repository.errors import TrendDataSourceError
from src.modules.sales_trend.service.sales_trend_cache import SalesTrendSnapshot, get_snapshot
from src.modules.trend_insights.adapters.factor_adapter import FactorSources
from src.modules.trend_insights.adapters.migration_adapter import TrendMigrationSnapshot, build_migration_snapshot
from src.modules.trend_insights.domain.affinity_group import MarketDiagnosis, compute_market_diagnosis, is_launch_affine
from src.modules.trend_insights.domain.cell_mode import diagnosis_mode
from src.modules.trend_insights.domain.constants import (
    AFFINE_GROUP_MIN_SCORE,
    AFFINE_GROUP_TOP_K,
    LOGGER_NAME,
    LOW_BASE_QUANTITY,
    LOW_BASE_REVENUE,
    MAX_GALLERY_DESCRIPTION_CHARS,
    MODE_NO_VARIATION,
    MODE_QUALITATIVE,
    RECENT_WINDOW_MAX_MONTHS_BEFORE_REFERENCE,
)
from src.modules.trend_insights.domain.decomposition import (
    CascadeResult,
    build_migration_parcels,
    convert_revenue_to_quantity,
    finalize_cascade,
    share_loss_without_migration,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage, MigrationPair, RawParcel
from src.modules.trend_insights.domain.factor_parcels import (
    PriceEvidence,
    build_lost_customers_parcel,
    build_price_parcel,
    build_promotion_indicator,
    build_seasonal_parcel,
    build_stockout_indicator,
    is_recent_base_month,
    month_day_weights,
    not_evaluated_indicator,
)
from src.modules.trend_insights.domain.exceptions import InsufficientBaseError, InvalidInsightParametersError, ProductNotFoundError
from src.modules.trend_insights.domain.ports import NotEvaluated, TrendSourceUnavailable
from src.modules.trend_insights.domain.privacy import RegionRow, detect_regional, group_regions
from src.modules.trend_insights.domain.windows import WindowSpec, build_window_spec
from src.modules.trend_insights.service.insights_service import InsightQuery
from src.modules.trend_insights.service.migration_cache import MigrationCache

logger = logging.getLogger(LOGGER_NAME + ".evidence")
UNAVAILABLE_SOURCE = "FONTE_INDISPONIVEL"
DEFAULT_FIRST_SALE_DATE = date(2025, 1, 1)
PCT_DECIMALS = 1
MONEY_DECIMALS = 2
MIGRATION_PARCEL_TYPES = ("PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR", "CANIBALIZACAO_OUTRO_FORNECEDOR")
OLD_BASE_MONTH = "MES_BASE_ANTIGO"
GALLERY_TEXT_SEPARATOR = "|||"  # separador canonico do documento de afinidade (canal nucleo | canal rico)


@dataclass(frozen=True)
class _Totals:
    """Totais efetivos (piso zero) de CUR e PRE de uma serie na metrica pedida."""

    current: Fraction
    previous: Fraction


@dataclass(frozen=True)
class _Context:
    """Entradas compartilhadas pelas parcelas e indicadores de uma mesma analise."""

    snapshot: SalesTrendSnapshot
    query: InsightQuery
    base_idx: int
    spec: WindowSpec
    cell: TrendCell
    revenue_cell: TrendCell
    direction: str
    base_adjusted: float
    is_recent_base: bool


@dataclass(frozen=True)
class _Promotions:
    """Promocao do SKU e dos afins em PRE e CUR (so SKUs, nunca cliente)."""

    own_pre: bool
    own_cur: bool
    affines_pre: frozenset
    affines_cur: frozenset

    @property
    def involves_own_product(self) -> bool:
        return self.own_pre or self.own_cur


def _empty_series(monthly_sales: MonthlySales) -> SkuSeries:
    zeros = (0,) * monthly_sales.month_count
    return SkuSeries(quantity=zeros, revenue=zeros, movement_mask=0)


def _effective(cell: TrendCell) -> _Totals:
    return _Totals(
        current=Fraction(max(0, cell.atual_bruto_escalado), VALUE_SCALE),
        previous=Fraction(max(0, cell.anterior_bruto_escalado), VALUE_SCALE),
    )


def _first_sale_month(series: SkuSeries, monthly_sales: MonthlySales) -> Optional[int]:
    for offset, value in enumerate(series.revenue):
        if value > 0:
            return monthly_sales.first_month + offset
    return None


class EvidenceBuilder:
    """Provedor de evidencias (`evidence_provider` do servico). Uma instancia por processo."""

    def __init__(
        self,
        migration_cache: MigrationCache,
        factor_sources: FactorSources,
        snapshot_provider: Callable[[], SalesTrendSnapshot] = get_snapshot,
    ):
        self._migration_cache = migration_cache
        self._sources = factor_sources
        self._snapshot_provider = snapshot_provider

    # ---------------------------------------------------------------- entrada
    def __call__(self, query: InsightQuery) -> EvidencePackage:
        snapshot = self._snapshot()
        base_idx = self._base_month_index(snapshot, query)
        entry = snapshot.catalog.get(query.sku)
        if entry is None:
            raise ProductNotFoundError()
        sales = snapshot.monthly_sales
        first_sale = sales.first_sale_date or DEFAULT_FIRST_SALE_DATE
        spec = build_window_spec(base_idx, query.window, query.comparison_mode, first_sale, snapshot.last_covered_day)
        cell, revenue = self._cells(snapshot, query.sku, base_idx, query)
        mode = diagnosis_mode(cell.status, cell.variacao_pct, cell.base_baixa)
        data = self._base_data(entry, query, base_idx, spec, cell, mode)
        if mode != MODE_NO_VARIATION:
            data.update(self._analysis(snapshot, query, base_idx, spec, cell, revenue, mode))
        return EvidencePackage.from_mapping(data, snapshot.reference_date)

    # ---------------------------------------------------------------- fontes da Tendencia
    def _snapshot(self) -> SalesTrendSnapshot:
        try:
            return self._snapshot_provider()
        except TrendDataSourceError:
            raise TrendSourceUnavailable() from None

    @staticmethod
    def _base_month_index(snapshot: SalesTrendSnapshot, query: InsightQuery) -> int:
        reference = snapshot.reference_date
        current_idx = month_index(reference.year, reference.month)
        base_idx = parse_base_month(query.base_month) if query.base_month else previous_month(current_idx)
        first_sale = snapshot.monthly_sales.first_sale_date or DEFAULT_FIRST_SALE_DATE
        try:
            validate_base_month(
                base_idx, month_index(first_sale.year, first_sale.month), current_idx, snapshot.last_covered_day)
        except InvalidTrendParametersError:
            raise InvalidInsightParametersError(("baseMonth",)) from None
        except BaseMonthWithoutSalesError:
            raise InsufficientBaseError() from None
        return base_idx

    @staticmethod
    def _cell(snapshot: SalesTrendSnapshot, sku: int, base_idx: int, query: InsightQuery, metric: str) -> TrendCell:
        sales = snapshot.monthly_sales
        series = sales.series.get(sku) or _empty_series(sales)
        return compute_cell(series, base_idx, query.window, metric, sales, snapshot.last_covered_day, query.comparison_mode)

    def _cells(self, snapshot, sku: int, base_idx: int, query: InsightQuery) -> Tuple[TrendCell, TrendCell]:
        """Celula na metrica pedida e celula em R$ (os gates de valor sao sempre em R$)."""
        cell = self._cell(snapshot, sku, base_idx, query, query.metric)
        revenue = cell if query.metric == "revenue" else self._cell(snapshot, sku, base_idx, query, "revenue")
        return cell, revenue

    # ---------------------------------------------------------------- dados base
    @staticmethod
    def _spans(spec: WindowSpec) -> Dict[str, Any]:
        one_day = timedelta(days=1)
        return {
            "atual": {"inicio": spec.cur_start.isoformat(), "fim": (spec.cur_end_exclusive - one_day).isoformat()},
            "anterior": {"inicio": spec.pre_start.isoformat(), "fim": (spec.pre_end_exclusive - one_day).isoformat()},
        }

    @staticmethod
    def _cell_dict(cell: TrendCell, window: int) -> Dict[str, Any]:
        """Serializa `TrendCell` no mesmo formato de `TrendCellSchema` (snake_case antes de `to_camel`)."""
        return {
            "meses": window,
            "atual": cell.atual,
            "anterior": cell.anterior,
            "variacao_pct": cell.variacao_pct,
            "status": cell.status,
            "base_parcial": cell.base_parcial,
            "base_baixa": cell.base_baixa,
            "devolucao_liquida": cell.devolucao_liquida,
            "atual_por_dia": cell.atual_por_dia,
            "anterior_por_dia": cell.anterior_por_dia,
        }

    def _base_data(self, entry, query: InsightQuery, base_idx: int, spec: WindowSpec, cell: TrendCell, mode: str):
        affinity = product_affinity_service.get_product_affinities(str(query.sku), top_k=1) or {}
        meta_status = "AVALIADO" if affinity else "NAO_AVALIADO"
        function, gallery_text = self._gallery_profile(query.sku)
        return {
            "produto": {
                "sku": query.sku, "descricao": entry.descricao, "fornecedor": entry.fornecedor,
                "categoria_galeria": affinity.get("category") or None,
                "funcao_primaria": function, "descricao_galeria": gallery_text,
            },
            "janela": {
                "metrica": query.metric, "janela": query.window, "mes_base": format_year_month(base_idx),
                "modo_comparacao": query.comparison_mode, **self._spans(spec),
            },
            "periodo": {"fator_ajuste": round(float(spec.scale_k), 6), "base_parcial": spec.is_partial_base,
                        "contigua": spec.is_contiguous},
            "celula": self._cell_dict(cell, query.window),
            "modo_diagnostico": mode, "cell_status": cell.status, "direcao": None,
            "variacao_pct": cell.variacao_pct, "delta_observado": None, "delta_receita": None,
            "base_ajustada": None, "residuo": None, "residual_share": None,
            "cascata": [], "indicadores": [], "afins": [],
            "diagnostico_mercado": {"classificacao": "NAO_AVALIADO" if meta_status == "NAO_AVALIADO" else "SEM_GRUPO_AFIM"},
            "impacto_outros": None, "regional": [],
        }

    @staticmethod
    def _gallery_profile(sku: int) -> Tuple[Optional[str], Optional[str]]:
        """Funcao primaria e texto da galeria do indice de afinidade (canal rico do documento, sem nome/marca)."""
        index = product_affinity_service.get_loaded_affinity_index() or {}
        meta = (index.get("skus") or {}).get(str(sku)) or {}
        doc = str(meta.get("doc") or "")
        text = doc.split(GALLERY_TEXT_SEPARATOR, 1)[1].strip() if GALLERY_TEXT_SEPARATOR in doc else ""
        return meta.get("primary_function") or None, text[:MAX_GALLERY_DESCRIPTION_CHARS] or None

    # ---------------------------------------------------------------- analise
    def _analysis(self, snapshot, query, base_idx, spec, cell, revenue_cell, mode) -> Dict[str, Any]:
        totals = _effective(cell)
        base_adjusted = totals.previous * spec.scale_k
        delta = totals.current - base_adjusted
        revenue_totals = _effective(revenue_cell)
        revenue_delta = revenue_totals.current - revenue_totals.previous * spec.scale_k
        ctx = _Context(snapshot, query, base_idx, spec, cell, revenue_cell, "QUEDA" if delta < 0 else "ALTA",
                       float(base_adjusted), self._is_recent(snapshot, base_idx))
        affines, market = self._affinity_group(snapshot, query, base_idx, spec, totals)
        migration = self._migration(snapshot, query, base_idx, spec)
        promotions = self._promotions(ctx, {a["sku"] for a in affines})
        raws = self._parcels(ctx, migration, promotions)
        quantitative = mode != MODE_QUALITATIVE
        cascade = finalize_cascade(
            float(delta) if quantitative else None, float(base_adjusted) if quantitative else None, raws, mode)
        indicators, regional = self._indicators(ctx, float(revenue_delta), cascade, market, promotions)
        return {
            "direcao": ctx.direction, "delta_observado": float(delta), "delta_receita": float(revenue_delta),
            "base_ajustada": float(base_adjusted), "residuo": cascade.residuo,
            "residual_share": self._residual_share(cascade, float(delta)),
            "cascata": self._cascade_dicts(cascade, float(base_adjusted)), "indicadores": indicators,
            "afins": affines, "diagnostico_mercado": self._market_dict(market), "regional": regional,
        }

    @staticmethod
    def _is_recent(snapshot: SalesTrendSnapshot, base_idx: int) -> bool:
        """Fatores de hoje (churn, estoque) so valem para o Mes-Base recente (P-164.2, P-165)."""
        reference = snapshot.reference_date
        return is_recent_base_month(
            base_idx, month_index(reference.year, reference.month), RECENT_WINDOW_MAX_MONTHS_BEFORE_REFERENCE)

    @staticmethod
    def _residual_share(cascade: CascadeResult, delta: float) -> Optional[float]:
        if cascade.residuo is None or not delta:
            return None
        return abs(cascade.residuo) / abs(delta)

    # ---------------------------------------------------------------- grupo afim
    def _affinity_group(self, snapshot, query, base_idx, spec, totals: _Totals):
        info = product_affinity_service.get_product_affinities(str(query.sku), top_k=AFFINE_GROUP_TOP_K)
        if info is None:
            return [], MarketDiagnosis(classificacao="NAO_AVALIADO")
        selected: List[Tuple[Mapping[str, Any], TrendCell]] = []
        group_pre, group_cur = Fraction(0), Fraction(0)
        for neighbor in info["affinities"]:
            sku = int(neighbor["sku"])
            if neighbor["affinityScore"] < AFFINE_GROUP_MIN_SCORE or sku not in snapshot.catalog:
                continue
            cell = self._cell(snapshot, sku, base_idx, query, query.metric)
            neighbor_totals = _effective(cell)
            group_pre += neighbor_totals.previous * spec.scale_k
            group_cur += neighbor_totals.current
            selected.append((neighbor, cell))
        launches = self._launch_skus(snapshot, query, spec, [int(n["sku"]) for n, _ in selected])
        affines = [
            self._affine_dict(neighbor, cell, query.window, int(neighbor["sku"]) in launches)
            for neighbor, cell in selected
        ]
        min_base = LOW_BASE_REVENUE if query.metric == "revenue" else LOW_BASE_QUANTITY
        base_adjusted = totals.previous * spec.scale_k
        market = compute_market_diagnosis(
            float(base_adjusted), float(totals.current), float(group_pre), float(group_cur), min_base)
        return affines, market

    @classmethod
    def _affine_dict(
        cls, neighbor: Mapping[str, Any], cell: TrendCell, window: int = 3, lancamento: bool = False,
    ) -> Dict[str, Any]:
        return {
            "sku": int(neighbor["sku"]), "descricao": neighbor.get("description"), "fornecedor": neighbor.get("supplier"),
            "same_supplier": bool(neighbor.get("sameSupplier")), "affinity_score": float(neighbor["affinityScore"]),
            "variacao_pct": cell.variacao_pct, "celula": cls._cell_dict(cell, window),
            "ganhou_clientes_do_produto": False, "lancamento": lancamento,
            "categoria_galeria": neighbor.get("galleryCategory") or None, "valor_venda_atual": neighbor.get("currentPrice"),
        }

    @staticmethod
    def _market_dict(market: MarketDiagnosis) -> Dict[str, Any]:
        return {
            "classificacao": market.classificacao,
            "variacao_mercado_pct": _round(market.variacao_mercado_pct, PCT_DECIMALS),
            "efeito_mercado": _round(market.efeito_mercado, MONEY_DECIMALS),
            "efeito_participacao": _round(market.efeito_participacao, MONEY_DECIMALS),
            "participacao_anterior_pct": _round(market.participacao_anterior_pct, PCT_DECIMALS),
            "participacao_atual_pct": _round(market.participacao_atual_pct, PCT_DECIMALS),
            "variacao_participacao_pp": _round(market.variacao_participacao_pp, PCT_DECIMALS),
        }

    # ---------------------------------------------------------------- migracao
    def _migration(self, snapshot, query, base_idx, spec: WindowSpec) -> Any:
        key = (query.comparison_mode, query.window, format_year_month(base_idx), snapshot.reference_date.isoformat(),
               self._index_generation())
        try:
            return self._migration_cache.get_or_build(key)
        except AnalyticsDataSourceError:
            raise TrendSourceUnavailable() from None

    @staticmethod
    def _index_generation() -> str:
        index = product_affinity_service.get_loaded_affinity_index()
        meta = (index or {}).get("meta") or {}
        return str(meta.get("last_sync_at") or meta.get("generatedAt") or "none")

    def _parcels(self, ctx: "_Context", migration, promotions) -> List[RawParcel]:
        raws = [self._seasonal_parcel(ctx), self._price_parcel(ctx, promotions)]
        raws += self._migration_parcels(ctx, migration)
        raws.append(self._lost_parcel(ctx, migration))
        return raws

    def _seasonal_parcel(self, ctx: "_Context") -> RawParcel:
        seasonality = self._sources.seasonality(ctx.query.sku)
        if isinstance(seasonality, NotEvaluated):
            return RawParcel(tipo="SAZONALIDADE", valor=None, status="NAO_AVALIADO", motivo=seasonality.reason)
        spec = ctx.spec
        return build_seasonal_parcel(
            seasonality, ctx.base_adjusted,
            month_day_weights(spec.cur_start, spec.cur_end_exclusive),
            month_day_weights(spec.pre_start, spec.pre_end_exclusive))

    def _price_parcel(self, ctx: "_Context", promotions) -> RawParcel:
        elasticity = self._sources.elasticity(ctx.query.sku)
        if isinstance(elasticity, NotEvaluated):
            return RawParcel(tipo="PRECO", valor=None, status="NAO_AVALIADO", motivo=elasticity.reason)
        query, quantity_cell = ctx.query, ctx.cell
        if query.metric != "quantity":
            quantity_cell = self._cell(ctx.snapshot, query.sku, ctx.base_idx, query, "quantity")
        qty, rev = _effective(quantity_cell), _effective(ctx.revenue_cell)
        return build_price_parcel(PriceEvidence(
            metric=query.metric, qty_pre=float(qty.previous), rev_pre=float(rev.previous), qty_cur=float(qty.current),
            rev_cur=float(rev.current), scale_k=float(ctx.spec.scale_k), elasticity=elasticity.elasticity,
            is_reliable=elasticity.is_reliable, is_fallback=elasticity.is_fallback,
            confidence_level=elasticity.confidence_level,
            is_promotion_involved=isinstance(promotions, _Promotions) and promotions.involves_own_product))

    def _migration_parcels(self, ctx: "_Context", migration) -> List[RawParcel]:
        if isinstance(migration, NotEvaluated) or not isinstance(migration, TrendMigrationSnapshot):
            reason = migration.reason if isinstance(migration, NotEvaluated) else UNAVAILABLE_SOURCE
            return [RawParcel(tipo=t, valor=None, status="NAO_AVALIADO", motivo=reason) for t in MIGRATION_PARCEL_TYPES]
        pairs = self._pairs(ctx.snapshot, ctx.query.sku, migration, ctx.direction)
        launches = self._launch_skus(ctx.snapshot, ctx.query, ctx.spec, [p.sku for p in pairs])
        parcels = build_migration_parcels(pairs, launches, ctx.direction)
        return [self._convert_units(parcels[t], ctx.query, ctx.spec, ctx.cell, ctx.revenue_cell)
                for t in MIGRATION_PARCEL_TYPES]

    @staticmethod
    def _lost_parcel(ctx: "_Context", migration) -> RawParcel:
        """Clientes perdidos so na queda e so com o snapshot de migracao (o churn e lido la, P-164.3)."""
        if ctx.direction != "QUEDA":
            return RawParcel(tipo="CLIENTES_PERDIDOS", valor=None, status="SEM_EFEITO", motivo="NAO_SE_APLICA_A_ALTA")
        if isinstance(migration, NotEvaluated):
            reason = migration.reason
        elif not isinstance(migration, TrendMigrationSnapshot):
            reason = UNAVAILABLE_SOURCE
        else:
            reason = migration.lost_unavailable_reason
        if reason:
            return RawParcel(tipo="CLIENTES_PERDIDOS", valor=None, status="NAO_AVALIADO", motivo=reason)
        return build_lost_customers_parcel(migration.lost_by_sku.get(str(ctx.query.sku)), ctx.query.metric)

    def _promotions(self, ctx: "_Context", affine_skus) -> Any:
        spec, sku = ctx.spec, ctx.query.sku
        before = self._sources.promotion_skus(spec.pre_start, spec.pre_end_exclusive)
        now = self._sources.promotion_skus(spec.cur_start, spec.cur_end_exclusive)
        if isinstance(before, NotEvaluated) or isinstance(now, NotEvaluated):
            return NotEvaluated(UNAVAILABLE_SOURCE)
        return _Promotions(
            own_pre=sku in before, own_cur=sku in now,
            affines_pre=frozenset(affine_skus & before), affines_cur=frozenset(affine_skus & now))

    @staticmethod
    def _convert_units(parcel: RawParcel, query: InsightQuery, spec: WindowSpec, cell, revenue_cell) -> RawParcel:
        if query.metric != "quantity" or parcel.valor is None:
            return parcel
        rev, qty = _effective(revenue_cell), _effective(cell)
        converted = convert_revenue_to_quantity(
            parcel.valor, float(rev.previous), float(rev.current), float(qty.previous), float(qty.current), float(spec.scale_k))
        if converted is None:
            return RawParcel(tipo=parcel.tipo, valor=None, status="NAO_AVALIADO", motivo="SEM_PRECO_MEDIO")
        return RawParcel(tipo=parcel.tipo, valor=converted, confianca=parcel.confianca, status=parcel.status,
                         itens=parcel.itens)

    @staticmethod
    def _pairs(snapshot, sku: int, migration: TrendMigrationSnapshot, direction: str) -> List[MigrationPair]:
        engine_result = migration.migration
        flows = getattr(engine_result, "pair_flows", {})
        target = str(sku)
        affinity_map = product_affinity_service.get_affinity_lookup_map() or {}
        pairs = []
        for (victim, cannibal), pair in flows.items():
            other = cannibal if direction == "QUEDA" else victim
            if (victim if direction == "QUEDA" else cannibal) != target or int(other) not in snapshot.catalog:
                continue
            other_entry, own_entry = snapshot.catalog[int(other)], snapshot.catalog[sku]
            same = bool(own_entry.fornecedor) and (other_entry.fornecedor or "").strip().upper() == own_entry.fornecedor.strip().upper()
            pairs.append(MigrationPair(
                sku=int(other), same_supplier=same, net_rev=pair.net_rev, net_clients=pair.net_clients,
                affinity_score=(affinity_map.get(target) or {}).get(other, 0.0),
                descricao=other_entry.descricao, fornecedor=other_entry.fornecedor))
        return pairs

    @staticmethod
    def _launch_skus(snapshot, query, spec: WindowSpec, candidates: List[int]) -> set:
        sales = snapshot.monthly_sales
        base_first = sales.first_sale_date or DEFAULT_FIRST_SALE_DATE
        launches = set()
        for sku in candidates:
            first_month = _first_sale_month(sales.series.get(sku) or _empty_series(sales), sales)
            if first_month is not None and is_launch_affine(
                    first_month, spec.pre_last_month_index, spec.cur_last_month_index, base_first):
                launches.add(sku)
        return launches

    # ---------------------------------------------------------------- indicadores
    def _indicators(self, ctx: "_Context", revenue_delta, cascade, market, promotions):
        indicators = [self._stockout_indicator(ctx, cascade), self._promotion_indicator(promotions)]
        regional_indicator, regional_rows = self._regional(ctx.query, ctx.spec, revenue_delta)
        indicators.append(regional_indicator)
        indicators.append(self._share_loss_indicator(market, cascade, revenue_delta))
        return indicators, regional_rows

    def _stockout_indicator(self, ctx: "_Context", cascade: CascadeResult) -> Dict[str, Any]:
        if not ctx.is_recent_base:
            return not_evaluated_indicator("RUPTURA", OLD_BASE_MONTH)
        stock = self._sources.current_stock(ctx.query.sku)
        if isinstance(stock, NotEvaluated):
            return not_evaluated_indicator("RUPTURA", stock.reason)
        has_migration_value = any(p.tipo in MIGRATION_PARCEL_TYPES and p.valor for p in cascade.parcels)
        return build_stockout_indicator(stock, has_migration_value)

    @staticmethod
    def _promotion_indicator(promotions) -> Dict[str, Any]:
        if not isinstance(promotions, _Promotions):
            return not_evaluated_indicator("PROMOCAO", UNAVAILABLE_SOURCE)
        return build_promotion_indicator(
            promotions.own_pre, promotions.own_cur, promotions.affines_pre, promotions.affines_cur)

    def _regional(self, query, spec: WindowSpec, revenue_delta: float):
        unavailable = {"tipo": "REGIONAL", "status": "NAO_AVALIADO", "valor": None,
                       "motivo_nao_avaliado": UNAVAILABLE_SOURCE, "evidencia": None}
        try:
            rows = sales_repository.fetch_sku_region_window_sales(
                query.sku, spec.pre_start, spec.pre_end_exclusive, spec.cur_start, spec.cur_end_exclusive)
        except AnalyticsDataSourceError:
            return unavailable, []
        grouping = group_regions([RegionRow(uf=r[0], pre_rev=r[2], cur_rev=r[4], clients=r[5]) for r in rows], float(spec.scale_k))
        if grouping.status != "AVALIADO":
            return {**unavailable, "motivo_nao_avaliado": grouping.motivo}, []
        regional_rows = [{"uf": g.uf, "delta": round(g.delta, MONEY_DECIMALS)} for g in grouping.groups]
        found = detect_regional(grouping, revenue_delta)
        if found.status != "AVALIADO":
            return {"tipo": "REGIONAL", "status": "SEM_EFEITO", "valor": None, "motivo_sem_efeito": "SEM_CONCENTRACAO",
                    "evidencia": None}, regional_rows
        evidence = {"ufConcentradora": found.uf_concentradora, "participacaoPct": round(found.participacao_pct, PCT_DECIMALS)}
        return {"tipo": "REGIONAL", "status": "AVALIADO", "valor": None, "confianca": "MEDIA", "evidencia": evidence}, regional_rows

    @staticmethod
    def _share_loss_indicator(market: MarketDiagnosis, cascade: CascadeResult, delta: float) -> Dict[str, Any]:
        skipped = {"tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "SEM_EFEITO", "valor": None,
                   "motivo_sem_efeito": "SEM_CONCENTRACAO", "evidencia": None}
        if cascade.residuo is None or market.efeito_participacao is None or not delta:
            return skipped
        migration_total = sum(p.valor or 0.0 for p in cascade.parcels if p.tipo in (
            "PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR", "CANIBALIZACAO_OUTRO_FORNECEDOR"))
        found = share_loss_without_migration(market.efeito_participacao, migration_total, delta, cascade.residuo)
        if found is None:
            return skipped
        return {"tipo": "PERDA_PARTICIPACAO_SEM_MIGRACAO", "status": "AVALIADO", "valor": round(found.valor, MONEY_DECIMALS),
                "confianca": "BAIXA", "evidencia": {"afinsQueCresceramSemClientesDoProduto": []}}

    # ---------------------------------------------------------------- serializacao da cascata
    @staticmethod
    def _cascade_dicts(cascade: CascadeResult, base_adjusted: float) -> List[Dict[str, Any]]:
        result = []
        for parcel in cascade.parcels:
            points = None if parcel.valor is None or not base_adjusted else round(parcel.valor / base_adjusted * 100, PCT_DECIMALS)
            result.append({
                "tipo": parcel.tipo, "status": parcel.status, "valor": _round(parcel.valor, MONEY_DECIMALS),
                "pontos_percentuais": points, "sentido": parcel.sentido, "explicativa": parcel.explicativa,
                "cortada": parcel.cortada, "confianca": parcel.confianca,
                "motivo_nao_avaliado": parcel.motivo if parcel.status == "NAO_AVALIADO" else None,
                "motivo_sem_efeito": parcel.motivo if parcel.status == "SEM_EFEITO" else None,
                "detalhe": dict(parcel.detalhe) if parcel.detalhe else None,
                "itens": [{
                    "sku": i.sku, "descricao": i.descricao, "fornecedor": i.fornecedor, "same_supplier": i.same_supplier,
                    "affinity_score": round(i.affinity_score, 3), "lancamento": i.lancamento,
                    "receita_migrada": _round(i.receita_migrada if cascade.residuo is not None else None, MONEY_DECIMALS),
                    "clientes_migrados": i.clientes_migrados, "confianca": i.confianca,
                } for i in parcel.itens],
            })
        return result


def _round(value: Optional[float], decimals: int) -> Optional[float]:
    return None if value is None else round(value, decimals)


def make_migration_builder(snapshot_provider=get_snapshot, factor_sources: Optional[FactorSources] = None):
    """Builder do `MigrationCache`: recompoe as janelas da chave e le o SQL (uma vez por janela, P-153).
    O churn (codigos de clientes perdidos) e lido aqui, so para Mes-Base recente, e descartado com as linhas."""

    def build(key) -> Any:
        mode, window, base_month, reference_iso, _generation = key
        snapshot = snapshot_provider()
        sales = snapshot.monthly_sales
        first_sale = sales.first_sale_date or DEFAULT_FIRST_SALE_DATE
        base_idx = parse_base_month(base_month)
        spec = build_window_spec(base_idx, window, mode, first_sale, snapshot.last_covered_day)
        catalog = {
            str(sku): {"sku": str(sku), "description": e.descricao, "supplier": e.fornecedor or "", "active": True}
            for sku, e in snapshot.catalog.items()
        }
        lost_codes, lost_reason = _lost_customer_codes(snapshot, base_idx, factor_sources)
        return build_migration_snapshot(
            spec=spec, affinity_map=product_affinity_service.get_affinity_lookup_map(), catalog=catalog,
            lost_customer_codes=lost_codes, lost_unavailable_reason=lost_reason)

    return build


def _lost_customer_codes(snapshot, base_idx: int, factor_sources: Optional[FactorSources]):
    """`(codigos, motivo)`: churn so para Mes-Base recente (P-164.2); fonte ausente nao derruba (P-173)."""
    reference = snapshot.reference_date
    is_recent = is_recent_base_month(
        base_idx, month_index(reference.year, reference.month), RECENT_WINDOW_MAX_MONTHS_BEFORE_REFERENCE)
    if not is_recent:
        return frozenset(), OLD_BASE_MONTH
    codes = factor_sources.lost_customer_codes() if factor_sources is not None else NotEvaluated(UNAVAILABLE_SOURCE)
    if isinstance(codes, NotEvaluated):
        return frozenset(), codes.reason
    return codes, None
