"""
Motor de Domínio Puro — F6 v2: Relatório Global de Canibalização por Migração de Clientes
e Equilíbrio de Preço (P-128 a P-138; ADR-007 v2; LGPD-CAN-01..06).

Módulo estritamente puro (sem I/O, sem SQL, sem FastAPI):
- P-128: Janelas comparáveis (PRE vs CUR) de 30/60/90 dias e truncamento de saldos negativos.
- P-129: Elegibilidade de produto vítima (catálogo ativo com Tipo, PRE >= R$ 500, queda >= minDropPct).
- P-130: Migração direcional bruta na mesma categoria com conservação de fluxo (sem dupla contagem).
- P-131: Desconto de fluxo reverso (migração direcional líquida) e corte mínimo de clientes.
- P-132: Quantificação de faturamento canibalizado (R$ e %) e KPIs consolidados.
- P-133: Preço de referência, gap percentual, margem unitária com fallback 60% e impacto de margem.
- P-134: Classificação do mecanismo (PRECO_MENOR_DESTROI_MARGEM / MARGEM_PRESERVADA / MIGRACAO_POR_VALOR).
- P-135: Motor de equilíbrio de preço (fechamento ~40% do gap, piso de margem 20%, teto +12%).
- P-136: Relatório global (filtros, ordenação) e detalhe por vítima.
- LGPD-CAN-04: Dicionário volátil `by_cli` descartado explicitamente (`del by_cli`) antes do retorno.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union
import unicodedata

from src.modules.analytics.domain.exceptions import (
    CannibalizationInsufficientHistoryError,
    CannibalizationInvalidParametersError,
    CannibalizationProductNotFoundError,
)

# ---------------------------------------------------------------------------
# Constantes de Negócio (P-128 a P-137 — zero números mágicos)
# ---------------------------------------------------------------------------

ALLOWED_WINDOW_DAYS: Tuple[int, ...] = (30, 60, 90)
DEFAULT_WINDOW_DAYS: int = 90
RETURN_OPERATION_PATTERN: str = "DEVOLU%"
MIN_PRE_REVENUE: float = 500.0
DEFAULT_MIN_DROP_PCT: float = 5.0
MIN_DROP_PCT_LOWER: float = 1.0
MIN_DROP_PCT_UPPER: float = 80.0
DEFAULT_MIN_MIGRATED_CLIENTS: int = 3
MIN_MIGRATED_CLIENTS_LOWER: int = 1
MIN_MIGRATED_CLIENTS_UPPER: int = 50
COST_FALLBACK_RATIO: float = 0.60
PRICE_GAP_THRESHOLD_PCT: float = 3.0
GAP_REDUCTION_TARGET: float = 0.40
MIN_CONTRIBUTION_MARGIN_PCT: float = 0.20
MAX_CANNIBAL_PRICE_HIKE_PCT: float = 0.12
MAX_CANNIBALIZERS_PER_VICTIM: int = 10
CACHE_TTL_HOURS: int = 6
MAX_SEARCH_LENGTH: int = 80

MECHANISM_DESTROYS_MARGIN: str = "PRECO_MENOR_DESTROI_MARGEM"
MECHANISM_PRESERVES_MARGIN: str = "PRECO_MENOR_MARGEM_PRESERVADA"
MECHANISM_VALUE_MIGRATION: str = "MIGRACAO_POR_VALOR"
ALLOWED_MECHANISMS: Tuple[str, ...] = (
    MECHANISM_DESTROYS_MARGIN,
    MECHANISM_PRESERVES_MARGIN,
    MECHANISM_VALUE_MIGRATION,
)


# ---------------------------------------------------------------------------
# Estruturas Imutáveis de Domínio (LGPD-CAN-02/05: zero Cod Cliente)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PeriodRange:
    """Intervalo inclusivo de exibição (AAAA-MM-DD) de uma janela."""

    start_date: date
    end_date: date


@dataclass(frozen=True)
class WindowBoundaries:
    """Limites temporais calculados para PRE [pre_start, mid) e CUR [mid, ref)."""

    pre_start: date
    mid_date: date
    reference_date: date
    pre_period: PeriodRange
    cur_period: PeriodRange


@dataclass(frozen=True)
class SkuPeriodTotals:
    """Totais agregados por SKU nas janelas PRE e CUR (sem identificadores de cliente)."""

    pre_qty: float
    pre_rev: float
    cur_qty: float
    cur_rev: float


@dataclass(frozen=True)
class DirectedMigrationPair:
    """Fluxo direcional líquido agregado do par (Vítima A -> Canibalizador B)."""

    victim_sku: str
    cannibal_sku: str
    gross_rev: float
    reverse_rev: float
    net_rev: float
    gross_clients: int
    reverse_clients: int
    net_clients: int


@dataclass(frozen=True)
class MigrationSnapshot:
    """
    Snapshot agregado cacheável da janela `(windowDays, referenceDate)` (ADR-007 DA-05).
    Garante LGPD-CAN-04/05: contém apenas totais por SKU e pares agregados, zero `Cod Cliente`.
    Todos os campos têm chaves `str` para serialização segura via `asdict` / JSON.
    """

    sku_totals: Mapping[str, SkuPeriodTotals]
    pairs_by_victim: Mapping[str, Tuple[DirectedMigrationPair, ...]]
    has_sufficient_history: bool

    @property
    def pair_flows(self) -> Dict[Tuple[str, str], DirectedMigrationPair]:
        """Visão indexada por `(victim_sku, cannibal_sku)` sobre os pares agregados."""
        return {
            (pair.victim_sku, pair.cannibal_sku): pair
            for pairs in self.pairs_by_victim.values()
            for pair in pairs
        }


@dataclass(frozen=True)
class PriceEquilibriumResult:
    """Resultado completo de comparação de preço, margem e equilíbrio (P-133..P-135)."""

    victim_unit_cost: float
    victim_unit_margin: float
    victim_margin_pct: float
    victim_cost_fallback_used: bool
    cannibal_unit_cost: float
    cannibal_unit_margin: float
    cannibal_margin_pct: float
    cannibal_cost_fallback_used: bool
    price_gap_pct: float
    net_margin_impact: float
    mechanism: str
    victim_margin_floor_price: float
    suggested_victim_price: float
    suggested_cannibal_price: float
    projected_price_gap_pct: float
    action_summary: str


@dataclass(frozen=True)
class CannibalizerEvaluation:
    """Diagnóstico completo de um canibalizador B em relação à vítima A."""

    sku: str
    description: str
    category: str
    supplier: str
    migrated_clients: int
    gross_clients_to_cannibal: int
    reverse_clients_to_victim: int
    migrated_revenue: float
    share_of_cannibalization_pct: float
    pre_revenue: float
    cur_revenue: float
    current_price: float
    unit_cost: float
    unit_margin: float
    margin_pct: float
    cost_fallback_used: bool
    current_stock: int
    price_gap_pct: float
    net_margin_impact: float
    mechanism: str
    suggested_victim_price: float
    suggested_cannibal_price: float
    projected_price_gap_pct: float
    victim_margin_floor_price: float
    action_summary: str


@dataclass(frozen=True)
class VictimEvaluation:
    """Diagnóstico consolidado de um produto vítima A e seus canibalizadores."""

    sku: str
    description: str
    category: str
    supplier: str
    pre_revenue: float
    cur_revenue: float
    revenue_drop: float
    revenue_drop_pct: float
    cannibalized_revenue: float
    cannibalized_revenue_pct: float
    drop_explained_pct: float
    current_price: float
    unit_cost: float
    unit_margin: float
    margin_pct: float
    cost_fallback_used: bool
    current_stock: int
    cannibalizer_count: int
    net_margin_impact: float
    top_cannibal: Optional[CannibalizerEvaluation]
    cannibalizers: List[CannibalizerEvaluation]


@dataclass(frozen=True)
class ReportKpis:
    """KPIs globais do relatório de canibalização (P-132.4)."""

    total_victims: int
    total_cannibalized_revenue: float
    avg_cannibalized_revenue_pct: float
    total_net_margin_impact: float
    margin_destroying_pairs_count: int


@dataclass(frozen=True)
class CannibalizationReportResult:
    """Resultado de domínio do Relatório Global de Canibalização (P-136.1)."""

    kpis: ReportKpis
    available_categories: List[str]
    available_suppliers: List[str]
    victims: List[VictimEvaluation]


@dataclass(frozen=True)
class CannibalizationDetailResult:
    """Resultado de domínio do Detalhe por SKU Vítima (P-136.2)."""

    is_cannibalized: bool
    victim: VictimEvaluation
    cannibalizers: List[CannibalizerEvaluation]


# Alias de compatibilidade
CannibalizationVictimDetailResult = CannibalizationDetailResult


# ---------------------------------------------------------------------------
# Formatação pt-BR para resumo acionável (P-135.5)
# ---------------------------------------------------------------------------


def _fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_pct(value: float, signed: bool = False) -> str:
    fmt = f"{value:+.1f}%" if signed else f"{value:.1f}%"
    return fmt.replace(".", ",")


# ---------------------------------------------------------------------------
# P-128: Limites Temporais
# ---------------------------------------------------------------------------


def compute_window_boundaries(reference_date: date, window_days: int) -> WindowBoundaries:
    """
    Calcula os limites de `PRE` [D_ref - 2N, D_mid) e `CUR` [D_mid, D_ref) (P-128.1).

    Raises:
        CannibalizationInvalidParametersError: se `window_days` não pertencer a {30, 60, 90}.
    """
    if window_days not in ALLOWED_WINDOW_DAYS:
        raise CannibalizationInvalidParametersError(fields=["windowDays"])
    mid_date = reference_date - timedelta(days=window_days)
    pre_start = reference_date - timedelta(days=2 * window_days)
    return WindowBoundaries(
        pre_start=pre_start,
        mid_date=mid_date,
        reference_date=reference_date,
        pre_period=PeriodRange(start_date=pre_start, end_date=mid_date - timedelta(days=1)),
        cur_period=PeriodRange(start_date=mid_date, end_date=reference_date - timedelta(days=1)),
    )


# ---------------------------------------------------------------------------
# P-133, P-134 & P-135: Preço, Custo, Margem, Mecanismo e Equilíbrio de Preço
# ---------------------------------------------------------------------------


def resolve_reference_price(
    catalog_price: Optional[float],
    cur_rev: float,
    cur_qty: float,
    pre_rev: float,
    pre_qty: float,
) -> float:
    """Resolve preço de referência: Pc.Venda > preço médio CUR > preço médio PRE (P-133.1)."""
    if catalog_price is not None and float(catalog_price) > 0.0:
        return float(catalog_price)
    if cur_qty > 0.0 and cur_rev > 0.0:
        return float(cur_rev / cur_qty)
    if pre_qty > 0.0 and pre_rev > 0.0:
        return float(pre_rev / pre_qty)
    return 0.0


def resolve_cost_and_margin(
    price: float,
    last_cost: Optional[float],
) -> Tuple[float, float, float, bool]:
    """
    Calcula custo efetivo, margem unitária, razão de margem (0..1) e flag de fallback (P-133.3).
    Fallback: 60% do preço quando `Pc.Ultimo Custo` é nulo, <= 0 ou >= preço.
    """
    if price <= 0.0:
        return 0.0, 0.0, 0.0, True
    if last_cost is not None and 0.0 < float(last_cost) < price:
        eff_cost = float(last_cost)
        fallback_used = False
    else:
        eff_cost = price * COST_FALLBACK_RATIO
        fallback_used = True
    unit_margin = price - eff_cost
    margin_ratio = unit_margin / price
    return eff_cost, unit_margin, margin_ratio, fallback_used


def compute_price_gap_pct(victim_price: float, cannibal_price: float) -> float:
    """Gap percentual de preço ((P_A - P_B) / P_B) * 100 (P-133.2)."""
    if cannibal_price <= 0.0:
        return 0.0
    return ((victim_price - cannibal_price) / cannibal_price) * 100.0


def classify_mechanism(
    price_gap_pct: float,
    unit_margin_a: float,
    unit_margin_b: float,
    margin_ratio_a: float,
    margin_ratio_b: float,
) -> str:
    """Classifica o mecanismo de canibalização do par (Vítima A, Canibalizador B) (P-134)."""
    if price_gap_pct > PRICE_GAP_THRESHOLD_PCT:
        if unit_margin_b < unit_margin_a or margin_ratio_b < margin_ratio_a:
            return MECHANISM_DESTROYS_MARGIN
        return MECHANISM_PRESERVES_MARGIN
    return MECHANISM_VALUE_MIGRATION


def calculate_price_equilibrium(
    victim_price: float,
    victim_cost: Optional[float],
    cannibal_price: float,
    cannibal_cost: Optional[float],
    migrated_revenue: float,
    victim_stock: int = 0,
) -> PriceEquilibriumResult:
    """
    Motor determinístico completo de comparação de preço, margem e equilíbrio (P-133..P-135).
    Garante piso mínimo de 20% de margem na vítima e teto máximo de +12% no canibalizador.
    """
    price_a = float(victim_price or 0.0)
    price_b = float(cannibal_price or 0.0)
    eff_cost_a, unit_margin_a, margin_ratio_a, fallback_a = resolve_cost_and_margin(price_a, victim_cost)
    eff_cost_b, unit_margin_b, margin_ratio_b, fallback_b = resolve_cost_and_margin(price_b, cannibal_cost)

    gap_pct = compute_price_gap_pct(price_a, price_b)
    net_margin_impact = float(migrated_revenue) * (margin_ratio_b - margin_ratio_a)
    mechanism = classify_mechanism(gap_pct, unit_margin_a, unit_margin_b, margin_ratio_a, margin_ratio_b)

    floor_a = eff_cost_a / (1.0 - MIN_CONTRIBUTION_MARGIN_PCT) if eff_cost_a > 0.0 else 0.0
    cap_b = price_b * (1.0 + MAX_CANNIBAL_PRICE_HIKE_PCT)
    delta_p = price_a - price_b

    if mechanism == MECHANISM_VALUE_MIGRATION or delta_p <= 0.0 or price_b <= 0.0:
        pa_star = round(price_a, 2)
        pb_star = round(price_b, 2)
        projected_gap = round(compute_price_gap_pct(pa_star, pb_star), 2)
        stock_hint = (
            " (estoque atual zerado — priorizar reposição)"
            if victim_stock <= 0
            else f" (estoque atual: {victim_stock} un.)"
        )
        summary = (
            f"Migração por valor percebido sem distorção negativa de preço; manter preços atuais e "
            f"verificar ruptura de estoque, apresentação ou posicionamento comercial da vítima{stock_hint}."
        )
    else:
        if mechanism == MECHANISM_DESTROYS_MARGIN:
            delta_total = GAP_REDUCTION_TARGET * delta_p
            raw_pa = max(floor_a, price_a - 0.50 * delta_total)
            delta_a = max(0.0, price_a - raw_pa)
            delta_b = min(cap_b - price_b, delta_total - delta_a)
            raw_pb = price_b + max(0.0, delta_b)
        else:
            # MECHANISM_PRESERVES_MARGIN (P-135.3)
            raw_pa = max(floor_a, price_a - 0.25 * delta_p)
            raw_pb = min(cap_b, price_b + 0.15 * delta_p)

        pa_star = round(raw_pa, 2)
        pb_star = round(raw_pb, 2)
        projected_gap = round(compute_price_gap_pct(pa_star, pb_star), 2)

        pct_a = ((pa_star - price_a) / price_a * 100.0) if price_a > 0.0 else 0.0
        pct_b = ((pb_star - price_b) / price_b * 100.0) if price_b > 0.0 else 0.0

        parts: List[str] = []
        if abs(pa_star - round(price_a, 2)) >= 0.01:
            verb_a = "Reduzir" if pa_star < price_a else "Ajustar"
            parts.append(f"{verb_a} vítima para {_fmt_brl(pa_star)} ({_fmt_pct(pct_a, signed=True)})")
        else:
            parts.append(f"Manter vítima em {_fmt_brl(pa_star)} (no piso de margem de 20%)")

        if abs(pb_star - round(price_b, 2)) >= 0.01:
            parts.append(f"reajustar canibalizador para {_fmt_brl(pb_star)} ({_fmt_pct(pct_b, signed=True)})")
        else:
            parts.append(f"manter canibalizador em {_fmt_brl(pb_star)}")

        summary = (
            f"{parts[0]} e {parts[1]} para fechar o gap de "
            f"{_fmt_pct(gap_pct)} para {_fmt_pct(projected_gap)}."
        )

    return PriceEquilibriumResult(
        victim_unit_cost=round(eff_cost_a, 2),
        victim_unit_margin=round(unit_margin_a, 2),
        victim_margin_pct=round(margin_ratio_a * 100.0, 2),
        victim_cost_fallback_used=fallback_a,
        cannibal_unit_cost=round(eff_cost_b, 2),
        cannibal_unit_margin=round(unit_margin_b, 2),
        cannibal_margin_pct=round(margin_ratio_b * 100.0, 2),
        cannibal_cost_fallback_used=fallback_b,
        price_gap_pct=round(gap_pct, 2),
        net_margin_impact=round(net_margin_impact, 2),
        mechanism=mechanism,
        victim_margin_floor_price=round(floor_a, 2),
        suggested_victim_price=pa_star,
        suggested_cannibal_price=pb_star,
        projected_price_gap_pct=projected_gap,
        action_summary=summary,
    )


# ---------------------------------------------------------------------------
# P-130 & P-131: Migração Direcional Líquida com Conservação de Fluxo
# ---------------------------------------------------------------------------


def _unpack_row(row: Union[Mapping[str, object], Sequence[object]]) -> Tuple[object, object, object, object, object, object]:
    if isinstance(row, Mapping):
        return (
            row.get("customer_code"),
            row.get("sku"),
            row.get("pre_qty", 0.0),
            row.get("pre_rev", 0.0),
            row.get("cur_qty", 0.0),
            row.get("cur_rev", 0.0),
        )
    return row[0], row[1], row[2], row[3], row[4], row[5]


# ---------------------------------------------------------------------------
# P-130: Extração de Família/Afinidade de Produto (Agnóstica de Fornecedor)
# ---------------------------------------------------------------------------
# No ERP da Fitoherb, `Externo01.Produto.Tipo` representa a linha comercial do
# fornecedor (ex.: "LINHA MAX TITANIUM", "LINHA INTEGRALMEDICA"), o que impediria
# qualquer comparação entre fornecedores distintos. Por isso, a compatibilidade
# entre produtos substitutos é determinada pelos tokens nucleares da descrição
# (removendo marca/fornecedor, peso/embalagem, sabor e adjetivos genéricos),
# tratando todos os fornecedores com peso estritamente igual.

_QUANTITY_UNIT_RE = re.compile(
    r"\b\d+[.,]?\d*\s*(x\s*\d+[.,]?\d*)?\s*"
    r"(g|gr|grs|kg|mg|mcg|ml|l|ui|caps|cap|capsgel|comp|compr|cps|tabs|un|unid|saches|sache|gotas|gota)?\b"
)
_NEGATION_RE = re.compile(r"\b(?:s/|sem)\s+([a-z0-9]+)")
_DOTTED_ACRONYM_RE = re.compile(r"\b(?:[a-z]\.){2,}[a-z]?\.?")
_WORD_RE = re.compile(r"[a-z]{3,}")

_PRODUCT_TOKEN_STOPWORDS: FrozenSet[str] = frozenset(
    {
        # preposições / conectivos
        "de", "da", "do", "das", "dos", "com", "sem", "para", "por", "em", "na", "no", "e", "ou",
        # embalagens / formatos / unidades / linhas
        "caps", "capsula", "capsulas", "cap", "capsgel", "comp", "compr", "comprimido", "comprimidos",
        "cps", "tabs", "softgel", "softgels", "pote", "refil", "pouch", "sache", "saches", "display",
        "unid", "unidade", "unidades", "caixa", "frasco", "bisnaga", "tubo", "lata", "vidro",
        "gotas", "gota", "grs", "mcg", "stand", "ziper", "monodose", "peixinhos", "bala", "balas",
        "liquido", "liquida", "spray", "gel", "creme", "oleo", "extrato", "tablete", "tabletes",
        "goma", "gomas", "stick", "sticks", "shot", "shots", "dose", "doses", "kit",
        "suplemento", "alimentar", "composto", "composta", "complexo", "completo", "completa",
        "seco", "semente", "erva", "ervas", "misto", "especiarias", "farinha", "sal",
        "capilar", "corporal", "desodorizado", "std", "vita",
        # sabores / atributos sensoriais / cores genéricas
        "chocolate", "choco", "morango", "baunilha", "limao", "uva", "roxa", "laranja", "abacaxi", "maracuja",
        "melancia", "frutas", "vermelhas", "amarelas", "tropicais", "tangerina", "pessego", "coco", "banana", "maca",
        "canela", "menta", "hortela", "neutro", "neutra", "natural", "cookies", "brigadeiro", "caramelo", "cafe",
        "cappuccino", "pacoca", "doce", "leite", "avela", "pistache", "cramberry", "cranberry", "acai", "guarana",
        "framboesa", "cereja", "kiwi", "manga", "limonada", "suico", "belga", "branco", "preto", "amargo", "salgado",
        "verde", "vermelho", "amarelo", "roxo", "branca", "preta",
        "fruit", "punch", "pink", "lemonade", "cotton", "candy", "iced", "ice", "green", "apple", "berry", "citrus",
        "banoffe", "cocada", "mocaccino", "chantilly", "tutti", "frutti", "belo",
        "tradicional", "original", "sabor", "zero", "acucar", "lactose", "gluten", "vegano", "vegana", "integral",
        # qualificadores de marketing / genéricos
        "pura", "puro", "pure", "purissimo", "turbo", "hardcore", "ultra", "super", "plus", "max", "maxima",
        "pro", "top", "gold", "black", "premium", "master", "extreme", "forte", "extra", "nova", "novo", "formula",
        "kids", "senior", "fases", "fem", "men", "woman", "sport", "fitness", "daily", "dia", "noite",
        "concentrado", "concentrada", "isolado", "isolada", "hidrolisado", "hidrolisada",
        "monohidratada", "monohidratado", "monohid", "micronizada", "micronizado", "quelato", "quelado",
        "complex", "blend", "mix", "carbo", "low", "diet", "light", "fit", "energy", "power", "active", "life",
        "saude", "bem", "estar", "linha", "promocao", "promo", "gratis", "leva", "pague", "edicao", "especial",
        "tasty", "crisp", "crunch", "mini", "big", "mega", "essential", "essentials",
        "vitamina", "vitaminas", "dado", "torta",
    }
)

_CANONICAL_SYNONYMS: Tuple[Tuple[str, str], ...] = (
    ("colagentek", "colageno"),
    ("omegafor", "omega"),
    ("omega 3", "omega"),
    ("omega-3", "omega"),
    ("nutriwhey", "whey"),
    ("iso whey", "whey"),
    ("vitamina d3", "vitaminad"),
    ("vitamina d", "vitaminad"),
    ("vita d3", "vitaminad"),
    ("vit d3", "vitaminad"),
    ("vit d", "vitaminad"),
    ("d3 + c", "vitaminad + vitaminac"),
    ("+ c +", "+ vitaminac +"),
    ("vitamina b12", "vitaminab12"),
    ("metilcobalamina", "vitaminab12"),
    ("vitamina c", "vitaminac"),
    ("vitamina k2", "vitaminak2"),
    ("vitamina e", "vitaminae"),
    ("coenzima q10", "coq10"),
    ("coq 10", "coq10"),
    ("pre treino", "pretreino"),
    ("pre-treino", "pretreino"),
    ("pasta de amendoim", "pastaamendoim"),
    ("pasta amendoim", "pastaamendoim"),
    ("beta alanina", "betaalanina"),
    ("beta-alanina", "betaalanina"),
    ("barra de proteina", "barraproteina"),
    ("protein bar", "barraproteina"),
    ("l-carnitina", "lcarnitina"),
    ("l carnitina", "lcarnitina"),
    ("acido hialuronico", "hialuronico"),
    ("cha verde", "chaverde"),
    ("cha preto", "chapreto"),
    ("cafe verde", "cafeverde"),
    ("banana verde", "bananaverde"),
    ("maca verde", "macaverde"),
    ("erva doce", "ervadoce"),
    ("erva baleeira", "ervabaleeira"),
    ("erva de sao joao", "ervasaojoao"),
    ("erva de bicho", "ervabicho"),
    ("sal amargo", "salamargo"),
    ("sal de frutas", "salfrutas"),
    ("sal frutas", "salfrutas"),
    ("semente de abobora", "sementeabobora"),
    ("semente de uva", "sementeuva"),
    ("semente de girassol", "sementegirassol"),
    ("semente de linhaca", "sementelinhaca"),
    ("semente de chia", "sementechia"),
    ("rosa mosqueta", "rosamosqueta"),
    ("canela de velho", "canelavelho"),
    ("ora pro nobis", "orapronobis"),
    ("ora-pro-nobis", "orapronobis"),
    ("limao siciliano", "limaosiciliano"),
    ("vinagre de maca", "vinagremaca"),
    ("oleo de coco", "oleococo"),
    ("psilium", "psyllium"),
)


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _collect_supplier_tokens(catalog: Mapping[str, Mapping[str, object]]) -> FrozenSet[str]:
    tokens: Set[str] = set()
    for entry in catalog.values():
        supplier_raw = str(entry.get("supplier") or "").strip()
        if not supplier_raw:
            continue
        norm_sup = _strip_accents(supplier_raw.lower())
        for tok in _WORD_RE.findall(norm_sup):
            tokens.add(tok)
    return frozenset(tokens)


def _collapse_dotted_acronyms(text: str) -> str:
    """Converte siglas pontuadas como `b.o.p.e.` ou `b.c.a.a.` em `bope` / `bcaa`."""
    return _DOTTED_ACRONYM_RE.sub(lambda m: m.group(0).replace(".", ""), text)


def extract_product_family_tokens(
    description: str,
    supplier_tokens: FrozenSet[str] = frozenset(),
) -> FrozenSet[str]:
    """
    Extrai os tokens nucleares de família de produto a partir da descrição comercial,
    descartando marca/fornecedor, gramatura/embalagem, sabor e adjetivos genéricos.
    """
    text = _collapse_dotted_acronyms(_strip_accents(str(description or "").lower()))
    text = _NEGATION_RE.sub(r" sem_\1 ", text)
    for src, dst in _CANONICAL_SYNONYMS:
        if src in text:
            text = text.replace(src, dst)
    text = _QUANTITY_UNIT_RE.sub(" ", text)
    words = _WORD_RE.findall(text)
    return frozenset(
        w for w in words if w not in _PRODUCT_TOKEN_STOPWORDS and w not in supplier_tokens
    )


def compute_directional_migration(
    customer_sku_rows: Iterable[Union[Mapping[str, object], Sequence[object]]],
    catalog: Mapping[str, Mapping[str, object]],
    affinity_map: Optional[Mapping[str, Mapping[str, float]]] = None,
) -> MigrationSnapshot:
    """
    Constrói o snapshot agregado de migração direcional líquida a partir das linhas
    `(customer_code, sku, pre_qty, pre_rev, cur_qty, cur_rev)` (dict ou tupla).

    - P-128.2: Trunca saldos líquidos negativos de `(cliente, SKU, período)` em 0.0.
    - P-130: Conservação de fluxo por cliente entre produtos substitutos da mesma família
      (agnóstico de fornecedor — mesmo peso para qualquer fornecedor, sem dupla contagem),
      combinando o índice de afinidade semântica (`affinity_map`, quando disponível) com
      os tokens nucleares de produto.
    - P-131: Desconto de fluxo reverso (`net_rev`, `net_clients`).
    - LGPD-CAN-04: Descarta `by_cli` explicitamente (`del by_cli`) antes de retornar.
    """
    supplier_tokens = _collect_supplier_tokens(catalog)
    tokens_by_sku: Dict[str, FrozenSet[str]] = {
        sku_str: extract_product_family_tokens(str(entry.get("description") or ""), supplier_tokens)
        for sku_str, entry in catalog.items()
    }

    by_cli: Dict[int, Dict[str, Tuple[float, float]]] = {}
    sku_accum: Dict[str, List[float]] = {}
    has_any_pre = False
    has_any_cur = False

    for row in customer_sku_rows:
        raw_cust, raw_sku, raw_pre_qty, raw_pre_rev, raw_cur_qty, raw_cur_rev = _unpack_row(row)
        if raw_cust is None or raw_sku is None:
            continue
        sku_str = str(int(raw_sku))
        cat_entry = catalog.get(sku_str)
        if cat_entry is None or not cat_entry.get("active", True):
            continue

        pre_qty = max(0.0, float(raw_pre_qty or 0.0))
        pre_rev = max(0.0, float(raw_pre_rev or 0.0))
        cur_qty = max(0.0, float(raw_cur_qty or 0.0))
        cur_rev = max(0.0, float(raw_cur_rev or 0.0))

        if pre_rev <= 0.0 and cur_rev <= 0.0:
            continue

        if pre_rev > 0.0:
            has_any_pre = True
        if cur_rev > 0.0:
            has_any_cur = True

        acc = sku_accum.get(sku_str)
        if acc is None:
            sku_accum[sku_str] = [pre_qty, pre_rev, cur_qty, cur_rev]
        else:
            acc[0] += pre_qty
            acc[1] += pre_rev
            acc[2] += cur_qty
            acc[3] += cur_rev

        if not tokens_by_sku.get(sku_str) and not (affinity_map and affinity_map.get(sku_str)):
            continue

        cust_id = int(raw_cust)
        cli_skus = by_cli.get(cust_id)
        if cli_skus is None:
            cli_skus = {}
            by_cli[cust_id] = cli_skus
        prev_vals = cli_skus.get(sku_str)
        if prev_vals is None:
            cli_skus[sku_str] = (pre_rev, cur_rev)
        else:
            cli_skus[sku_str] = (prev_vals[0] + pre_rev, prev_vals[1] + cur_rev)

    gross_rev: Dict[Tuple[str, str], float] = {}
    gross_clients: Dict[Tuple[str, str], int] = {}

    for cli_skus in by_cli.values():
        if len(cli_skus) < 2:
            continue
        losses: List[Tuple[str, float]] = []
        gains: List[Tuple[str, float]] = []
        for sku_str, (pre_rev, cur_rev) in cli_skus.items():
            diff = pre_rev - cur_rev
            if diff > 0.0:
                losses.append((sku_str, diff))
            elif diff < 0.0:
                gains.append((sku_str, -diff))

        if not losses or not gains:
            continue

        # Alocação proporcional com conservação estrita de fluxo nos dois lados:
        # 1) cada perda A distribui `loss_a` entre os ganhos compatíveis B (qualquer fornecedor, mesmo peso);
        # 2) se a soma incidente em B exceder `gain_b`, escala por `gain_b / incoming[B]` (zero dupla contagem).
        tentative: List[Tuple[str, str, float, float]] = []
        incoming_by_gain: Dict[str, float] = {}
        for sku_a, loss_a in losses:
            tok_a = tokens_by_sku.get(sku_a, frozenset())
            aff_a = affinity_map.get(sku_a) if affinity_map else None
            if not tok_a and not aff_a:
                continue

            compat_gains: List[Tuple[str, float, float]] = []
            for sku_b, gain_b in gains:
                if affinity_map is not None:
                    aff_score = float(aff_a.get(sku_b, 0.0)) if aff_a else 0.0
                    if aff_score > 0.0:
                        compat_gains.append((sku_b, gain_b, gain_b * aff_score))
                else:
                    has_token_match = bool(tok_a and (tok_a & tokens_by_sku.get(sku_b, frozenset())))
                    if has_token_match:
                        compat_gains.append((sku_b, gain_b, gain_b))

            if not compat_gains:
                continue
            total_weighted_gain = sum(wg for _, _, wg in compat_gains)
            if total_weighted_gain <= 0.0:
                continue
            for sku_b, gain_b, weighted_gain in compat_gains:
                weight = loss_a * (weighted_gain / total_weighted_gain)
                tentative.append((sku_a, sku_b, weight, gain_b))
                incoming_by_gain[sku_b] = incoming_by_gain.get(sku_b, 0.0) + weight

        for sku_a, sku_b, weight, gain_b in tentative:
            incoming = incoming_by_gain[sku_b]
            scale = min(1.0, gain_b / incoming) if incoming > 0.0 else 0.0
            migrated = weight * scale
            if migrated > 0.0:
                pair_key = (sku_a, sku_b)
                gross_rev[pair_key] = gross_rev.get(pair_key, 0.0) + migrated
                gross_clients[pair_key] = gross_clients.get(pair_key, 0) + 1

    # LGPD-CAN-04: descarte explícito do dicionário com identificadores de clientes
    del by_cli

    # P-131: desconto do fluxo reverso (B -> A)
    pairs_map: Dict[str, List[DirectedMigrationPair]] = {}
    for (sku_a, sku_b), rev_ab in gross_rev.items():
        rev_ba = gross_rev.get((sku_b, sku_a), 0.0)
        cli_ab = gross_clients.get((sku_a, sku_b), 0)
        cli_ba = gross_clients.get((sku_b, sku_a), 0)
        net_rev = max(0.0, rev_ab - rev_ba)
        net_clients = max(0, cli_ab - cli_ba)
        if net_rev > 0.0 and net_clients > 0:
            pairs_map.setdefault(sku_a, []).append(
                DirectedMigrationPair(
                    victim_sku=sku_a,
                    cannibal_sku=sku_b,
                    gross_rev=rev_ab,
                    reverse_rev=rev_ba,
                    net_rev=net_rev,
                    gross_clients=cli_ab,
                    reverse_clients=cli_ba,
                    net_clients=net_clients,
                )
            )

    sku_totals = {
        sku_str: SkuPeriodTotals(
            pre_qty=vals[0],
            pre_rev=vals[1],
            cur_qty=vals[2],
            cur_rev=vals[3],
        )
        for sku_str, vals in sku_accum.items()
    }
    frozen_pairs: Dict[str, Tuple[DirectedMigrationPair, ...]] = {
        victim_sku: tuple(
            sorted(pair_list, key=lambda p: (-p.net_rev, -p.net_clients, p.cannibal_sku))
        )
        for victim_sku, pair_list in pairs_map.items()
    }

    return MigrationSnapshot(
        sku_totals=sku_totals,
        pairs_by_victim=frozen_pairs,
        has_sufficient_history=(has_any_pre and has_any_cur),
    )


# Alias
build_migration_snapshot = compute_directional_migration


# ---------------------------------------------------------------------------
# P-129, P-132..P-136: Avaliação de Vítimas, Relatório Global e Detalhe
# ---------------------------------------------------------------------------


def _validate_report_params(
    min_drop_pct: float,
    min_migrated_clients: int,
    mechanism: Optional[str] = None,
    search: Optional[str] = None,
) -> None:
    invalid: List[str] = []
    if not (MIN_DROP_PCT_LOWER <= min_drop_pct <= MIN_DROP_PCT_UPPER):
        invalid.append("minDropPct")
    if not (MIN_MIGRATED_CLIENTS_LOWER <= min_migrated_clients <= MIN_MIGRATED_CLIENTS_UPPER):
        invalid.append("minMigratedClients")
    if mechanism is not None and mechanism not in ALLOWED_MECHANISMS:
        invalid.append("mechanism")
    if search is not None and len(search) > MAX_SEARCH_LENGTH:
        invalid.append("search")
    if invalid:
        raise CannibalizationInvalidParametersError(fields=invalid)


def _evaluate_victim(
    sku_a: str,
    snapshot: MigrationSnapshot,
    catalog: Mapping[str, Mapping[str, object]],
    min_drop_pct: float,
    min_migrated_clients: int,
    require_eligible: bool = True,
) -> Optional[VictimEvaluation]:
    entry_a = catalog.get(sku_a)
    if entry_a is None or not entry_a.get("active", True):
        return None

    category_a = str(entry_a.get("category") or "").strip()
    supplier_a = str(entry_a.get("supplier") or "").strip()
    totals_a = snapshot.sku_totals.get(sku_a, SkuPeriodTotals(0.0, 0.0, 0.0, 0.0))

    pre_rev_a = totals_a.pre_rev
    cur_rev_a = totals_a.cur_rev
    revenue_drop_a = max(0.0, pre_rev_a - cur_rev_a)
    revenue_drop_pct_a = ((revenue_drop_a / pre_rev_a) * 100.0) if pre_rev_a > 0.0 else 0.0

    price_a = resolve_reference_price(
        entry_a.get("current_price"),
        totals_a.cur_rev,
        totals_a.cur_qty,
        totals_a.pre_rev,
        totals_a.pre_qty,
    )
    eff_cost_a, unit_margin_a, margin_ratio_a, fallback_a = resolve_cost_and_margin(
        price_a, entry_a.get("last_cost")
    )
    stock_a = int(entry_a.get("current_stock") or 0)

    is_eligible_drop = (
        bool(category_a)
        and pre_rev_a >= MIN_PRE_REVENUE
        and revenue_drop_a > 0.0
        and revenue_drop_pct_a >= min_drop_pct
    )

    valid_pairs: List[DirectedMigrationPair] = []
    if is_eligible_drop:
        raw_pairs = snapshot.pairs_by_victim.get(sku_a, ())
        valid_pairs = [
            p
            for p in raw_pairs
            if p.net_clients >= min_migrated_clients
            and p.net_rev > 0.0
            and p.cannibal_sku in catalog
            and catalog[p.cannibal_sku].get("active", True)
        ][:MAX_CANNIBALIZERS_PER_VICTIM]

    if not valid_pairs:
        if require_eligible:
            return None
        return VictimEvaluation(
            sku=sku_a,
            description=str(entry_a.get("description") or "").strip(),
            category=category_a,
            supplier=supplier_a,
            pre_revenue=round(pre_rev_a, 2),
            cur_revenue=round(cur_rev_a, 2),
            revenue_drop=round(revenue_drop_a, 2),
            revenue_drop_pct=round(revenue_drop_pct_a, 2),
            cannibalized_revenue=0.0,
            cannibalized_revenue_pct=0.0,
            drop_explained_pct=0.0,
            current_price=round(price_a, 2),
            unit_cost=round(eff_cost_a, 2),
            unit_margin=round(unit_margin_a, 2),
            margin_pct=round(margin_ratio_a * 100.0, 2),
            cost_fallback_used=fallback_a,
            current_stock=stock_a,
            cannibalizer_count=0,
            net_margin_impact=0.0,
            top_cannibal=None,
            cannibalizers=[],
        )

    total_migrated_rev = sum(p.net_rev for p in valid_pairs)
    cannibalized_rev = min(revenue_drop_a, total_migrated_rev)
    cannibalized_rev_pct = (cannibalized_rev / pre_rev_a) * 100.0 if pre_rev_a > 0.0 else 0.0
    drop_explained_pct = (cannibalized_rev / revenue_drop_a) * 100.0 if revenue_drop_a > 0.0 else 0.0

    cannibalizers: List[CannibalizerEvaluation] = []
    total_victim_margin_impact = 0.0

    for pair in valid_pairs:
        entry_b = catalog[pair.cannibal_sku]
        totals_b = snapshot.sku_totals.get(pair.cannibal_sku, SkuPeriodTotals(0.0, 0.0, 0.0, 0.0))
        price_b = resolve_reference_price(
            entry_b.get("current_price"),
            totals_b.cur_rev,
            totals_b.cur_qty,
            totals_b.pre_rev,
            totals_b.pre_qty,
        )
        eq = calculate_price_equilibrium(
            victim_price=price_a,
            victim_cost=entry_a.get("last_cost"),
            cannibal_price=price_b,
            cannibal_cost=entry_b.get("last_cost"),
            migrated_revenue=pair.net_rev,
            victim_stock=stock_a,
        )
        total_victim_margin_impact += eq.net_margin_impact
        share_pct = (pair.net_rev / total_migrated_rev) * 100.0 if total_migrated_rev > 0.0 else 0.0

        cannibalizers.append(
            CannibalizerEvaluation(
                sku=pair.cannibal_sku,
                description=str(entry_b.get("description") or "").strip(),
                category=str(entry_b.get("category") or "").strip(),
                supplier=str(entry_b.get("supplier") or "").strip(),
                migrated_clients=pair.net_clients,
                gross_clients_to_cannibal=pair.gross_clients,
                reverse_clients_to_victim=pair.reverse_clients,
                migrated_revenue=round(pair.net_rev, 2),
                share_of_cannibalization_pct=round(share_pct, 2),
                pre_revenue=round(totals_b.pre_rev, 2),
                cur_revenue=round(totals_b.cur_rev, 2),
                current_price=round(price_b, 2),
                unit_cost=eq.cannibal_unit_cost,
                unit_margin=eq.cannibal_unit_margin,
                margin_pct=eq.cannibal_margin_pct,
                cost_fallback_used=eq.cannibal_cost_fallback_used,
                current_stock=int(entry_b.get("current_stock") or 0),
                price_gap_pct=eq.price_gap_pct,
                net_margin_impact=eq.net_margin_impact,
                mechanism=eq.mechanism,
                suggested_victim_price=eq.suggested_victim_price,
                suggested_cannibal_price=eq.suggested_cannibal_price,
                projected_price_gap_pct=eq.projected_price_gap_pct,
                victim_margin_floor_price=eq.victim_margin_floor_price,
                action_summary=eq.action_summary,
            )
        )

    return VictimEvaluation(
        sku=sku_a,
        description=str(entry_a.get("description") or "").strip(),
        category=category_a,
        supplier=supplier_a,
        pre_revenue=round(pre_rev_a, 2),
        cur_revenue=round(cur_rev_a, 2),
        revenue_drop=round(revenue_drop_a, 2),
        revenue_drop_pct=round(revenue_drop_pct_a, 2),
        cannibalized_revenue=round(cannibalized_rev, 2),
        cannibalized_revenue_pct=round(cannibalized_rev_pct, 2),
        drop_explained_pct=round(drop_explained_pct, 2),
        current_price=round(price_a, 2),
        unit_cost=round(eff_cost_a, 2),
        unit_margin=round(unit_margin_a, 2),
        margin_pct=round(margin_ratio_a * 100.0, 2),
        cost_fallback_used=fallback_a,
        current_stock=stock_a,
        cannibalizer_count=len(cannibalizers),
        net_margin_impact=round(total_victim_margin_impact, 2),
        top_cannibal=cannibalizers[0],
        cannibalizers=cannibalizers,
    )


def build_cannibalization_report(
    snapshot: MigrationSnapshot,
    catalog: Mapping[str, Mapping[str, object]],
    min_drop_pct: float = DEFAULT_MIN_DROP_PCT,
    min_migrated_clients: int = DEFAULT_MIN_MIGRATED_CLIENTS,
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    mechanism: Optional[str] = None,
    search: Optional[str] = None,
) -> CannibalizationReportResult:
    """
    Constrói o Relatório Global de Canibalização sobre o snapshot cacheado (P-129..P-136.1).
    """
    _validate_report_params(
        min_drop_pct=min_drop_pct,
        min_migrated_clients=min_migrated_clients,
        mechanism=mechanism,
        search=search,
    )
    if not snapshot.has_sufficient_history:
        raise CannibalizationInsufficientHistoryError()

    all_victims: List[VictimEvaluation] = []
    for sku_a in snapshot.pairs_by_victim.keys():
        evaluated = _evaluate_victim(
            sku_a=sku_a,
            snapshot=snapshot,
            catalog=catalog,
            min_drop_pct=min_drop_pct,
            min_migrated_clients=min_migrated_clients,
            require_eligible=True,
        )
        if evaluated is not None:
            all_victims.append(evaluated)

    available_categories = sorted({v.category for v in all_victims if v.category})
    available_suppliers = sorted({v.supplier for v in all_victims if v.supplier})

    filtered = all_victims
    if category is not None and category.strip():
        cat_norm = category.strip().upper()
        filtered = [v for v in filtered if v.category.upper() == cat_norm]
    if supplier is not None and supplier.strip():
        sup_norm = supplier.strip().upper()
        filtered = [v for v in filtered if v.supplier.upper() == sup_norm]
    if mechanism is not None:
        filtered = [
            v for v in filtered if any(c.mechanism == mechanism for c in v.cannibalizers)
        ]
    if search is not None and search.strip():
        term = search.strip().lower()
        filtered = [
            v for v in filtered if term in v.sku.lower() or term in v.description.lower()
        ]

    filtered.sort(key=lambda v: (-v.cannibalized_revenue, -v.revenue_drop, v.sku))

    total_cannibalized_rev = sum(v.cannibalized_revenue for v in filtered)
    total_pre_rev = sum(v.pre_revenue for v in filtered)
    avg_cannibalized_pct = (
        (total_cannibalized_rev / total_pre_rev) * 100.0 if total_pre_rev > 0.0 else 0.0
    )
    total_margin_impact = sum(v.net_margin_impact for v in filtered)
    margin_destroying_count = sum(
        1 for v in filtered for c in v.cannibalizers if c.mechanism == MECHANISM_DESTROYS_MARGIN
    )

    kpis = ReportKpis(
        total_victims=len(filtered),
        total_cannibalized_revenue=round(total_cannibalized_rev, 2),
        avg_cannibalized_revenue_pct=round(avg_cannibalized_pct, 2),
        total_net_margin_impact=round(total_margin_impact, 2),
        margin_destroying_pairs_count=margin_destroying_count,
    )

    return CannibalizationReportResult(
        kpis=kpis,
        available_categories=available_categories,
        available_suppliers=available_suppliers,
        victims=filtered,
    )


def build_cannibalization_sku_detail(
    sku: str,
    snapshot: MigrationSnapshot,
    catalog: Mapping[str, Mapping[str, object]],
    min_drop_pct: float = DEFAULT_MIN_DROP_PCT,
    min_migrated_clients: int = DEFAULT_MIN_MIGRATED_CLIENTS,
) -> CannibalizationDetailResult:
    """
    Constrói o detalhe completo de uma vítima específica (P-136.2).
    - SKU fora do catálogo ativo -> CAN-001 (404).
    - Histórico insuficiente -> CAN-003 (422).
    - SKU ativo sem canibalização na janela -> is_cannibalized=False, cannibalizers=[].
    """
    _validate_report_params(
        min_drop_pct=min_drop_pct,
        min_migrated_clients=min_migrated_clients,
    )
    sku_str = str(sku)
    entry = catalog.get(sku_str)
    if entry is None or not entry.get("active", True):
        raise CannibalizationProductNotFoundError()

    if not snapshot.has_sufficient_history:
        raise CannibalizationInsufficientHistoryError()

    victim = _evaluate_victim(
        sku_a=sku_str,
        snapshot=snapshot,
        catalog=catalog,
        min_drop_pct=min_drop_pct,
        min_migrated_clients=min_migrated_clients,
        require_eligible=False,
    )
    assert victim is not None
    is_cannibalized = len(victim.cannibalizers) > 0
    return CannibalizationDetailResult(
        is_cannibalized=is_cannibalized,
        victim=victim,
        cannibalizers=victim.cannibalizers,
    )


# Alias de compatibilidade
build_cannibalization_victim_detail = build_cannibalization_sku_detail
