"""
Serviço de Aplicação para o Módulo de Previsão de Estoque e Compras (Contrato 2.0.0).

Orquestra o cache de catálogo e velocidade de vendas, o mapeamento da Política Mín/Máx
(P-053 a P-056), a configuração de parâmetros da tela e a geração do plano de compras em CSV.
Decisões de arquitetura: ADR-001 (DA-08, DA-10 e DA-11).
"""
from datetime import datetime, timezone
import io
import logging
import re
import threading
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from src.core.database import (
    fetch_sales_from_database,
    fetch_sales_velocity_from_database,
)
from src.etl import load_catalog_from_database, run_etl_pipeline
from src.modules.inventory.api.schemas import (
    InventoryConfigData,
    InventoryPredictRequest,
    RangeParameterConfig,
)
from src.modules.inventory.domain.inventory_engine import (
    ALL_SUPPLIERS_TOKENS,
    calculate_inventory_replenishment,
    calculate_sales_velocity,
    normalize_product_catalog,
    prepare_product_catalog,
)
from src.modules.inventory.domain.replenishment_policy import (
    DEFAULT_LEAD_TIME_DAYS,
    DEFAULT_MAX_COVERAGE_DAYS,
    DEFAULT_MIN_COVERAGE_DAYS,
    ReplenishmentPolicy,
)

logger = logging.getLogger(__name__)

# Faixas dos controles deslizantes do modal "Parâmetros" na tela (seção 3.1 do contrato 2.0.0 / A1).
UI_HISTORY_WINDOW_DAYS_DEFAULT = 60  # P-041 / P-053.1: janela padrão de vendas na tela
UI_HISTORY_WINDOW_DAYS_MIN = 15  # Limite mínimo do slider de janela de vendas
UI_HISTORY_WINDOW_DAYS_MAX = 180  # Limite máximo do slider de janela de vendas
UI_HISTORY_WINDOW_DAYS_STEP = 15  # Passo de incremento do slider de janela de vendas

UI_LEAD_TIME_DAYS_DEFAULT = DEFAULT_LEAD_TIME_DAYS  # P-055.3: lead time padrão na tela (15 dias)
UI_LEAD_TIME_DAYS_MIN = 1  # Limite mínimo do controle de lead time na tela
UI_LEAD_TIME_DAYS_MAX = 60  # Limite máximo do controle de lead time na tela (A5 mantido)
UI_LEAD_TIME_DAYS_STEP = 1  # Passo de incremento do controle de lead time

UI_MIN_COVERAGE_DAYS_DEFAULT = DEFAULT_MIN_COVERAGE_DAYS  # P-053.2: Dias Mínimo padrão (30 dias)
UI_MIN_COVERAGE_DAYS_MIN = 5  # A1: piso de Dias Mínimo no controle da tela
UI_MIN_COVERAGE_DAYS_MAX = 120  # A1: teto de Dias Mínimo no controle da tela
UI_MIN_COVERAGE_DAYS_STEP = 5  # A1: passo de incremento de Dias Mínimo na tela

UI_MAX_COVERAGE_DAYS_DEFAULT = DEFAULT_MAX_COVERAGE_DAYS  # P-053.2: Dias Máximo padrão (60 dias)
UI_MAX_COVERAGE_DAYS_MIN = 10  # A1: piso de Dias Máximo no controle da tela
UI_MAX_COVERAGE_DAYS_MAX = 180  # A1: teto de Dias Máximo no controle da tela
UI_MAX_COVERAGE_DAYS_STEP = 5  # A1: passo de incremento de Dias Máximo na tela

MILLISECONDS_PER_SECOND = 1000.0  # Fator de conversão de segundos para milissegundos
EXECUTION_TIME_DECIMALS = 2  # Casas decimais de executionTimeMs no envelope meta

CSV_UTF8_BOM = "\ufeff"  # BOM UTF-8 para abertura direta no Microsoft Excel em PT-BR
CSV_FIELD_SEPARATOR = ";"  # Separador de colunas padrão de planilhas brasileiras
CSV_DECIMAL_SEPARATOR = ","  # Separador decimal padrão brasileiro
CSV_FILENAME_PREFIX = "fitoherb_plano_compras"  # Prefixo canônico do arquivo exportado (seção 6.2)
CSV_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"  # Sufixo temporal AAAAMMDD_HHMMSS do arquivo CSV

# DA-11: sanitização estrita do slug de fornecedor no header Content-Disposition ([a-z0-9_]).
SUPPLIER_SLUG_SANITIZE_PATTERN = re.compile(r"[^a-z0-9_]+")
SUPPLIER_SLUG_COLLAPSE_PATTERN = re.compile(r"_+")

# P-056.5 / Seção 6.2 do contrato 2.0.0: mapeamento ordenado (17 colunas) do item para o CSV.
INVENTORY_CSV_COLUMNS: Mapping[str, str] = {
    "codigo": "Código",
    "descricao": "Descrição",
    "ean": "EAN",
    "fornecedor": "Fornecedor",
    "tipo": "Tipo/Linha",
    "estoqueAtual": "Estoque Físico Atual",
    "vmd": "Venda Média Diária (VMD)",
    "diasCobertura": "Dias de Cobertura",
    "leadTime": "Lead Time (Dias)",
    "estoqueMinimo": "Estoque Mínimo (un)",
    "estoqueMaximo": "Estoque Máximo (un)",
    "qtdSugeridaCompra": "Qtd Sugerida de Compra",
    "custoUnitario": "Último Custo Real (R$)",
    "precoVenda": "Preço de Venda (R$)",
    "investimentoTotalItem": "Investimento Total Sugerido (R$)",
    "statusLabel": "Status Operacional",
    "curvaAbc": "Curva ABC",
}

# Cache de velocidade de vendas e catálogo para alta performance
_INVENTORY_CACHE: Dict[str, Any] = {}
_VELOCITY_CACHE: Dict[int, pd.DataFrame] = {}
_INVENTORY_LOCK = threading.Lock()


def to_replenishment_policy(request: InventoryPredictRequest) -> ReplenishmentPolicy:
    """Converte o request validado da camada de API no objeto de valor `ReplenishmentPolicy`.

    Regra: P-053.2, P-053.3, P-055.3, A2 (ADR-001, DA-01 e DA-10).

    Args:
        request: Payload validado de `/predict` ou `/export-csv`.

    Returns:
        Instância imutável de `ReplenishmentPolicy`.
    """
    return ReplenishmentPolicy(
        min_coverage_days=request.minCoverageDays,
        max_coverage_days=request.maxCoverageDays,
        lead_time_days=request.leadTimeDays,
    )


def build_policy_echo(request: InventoryPredictRequest) -> Dict[str, int]:
    """Monta o bloco `data.politica` com os parâmetros efetivamente aplicados no cálculo.

    Regra: P-056.6 e ADR-001 (DA-08) — permite que a tela rotule os resultados com a política
    aplicada e reenvie exatamente os mesmos parâmetros na exportação CSV.

    Args:
        request: Payload validado com padrões aplicados.

    Returns:
        Dicionário com `historyWindowDays`, `leadTimeDays`, `minCoverageDays` e `maxCoverageDays`.
    """
    return {
        "historyWindowDays": request.historyWindowDays,
        "leadTimeDays": request.leadTimeDays,
        "minCoverageDays": request.minCoverageDays,
        "maxCoverageDays": request.maxCoverageDays,
    }


def get_inventory_parameter_config() -> InventoryConfigData:
    """Retorna os padrões e faixas dos controles deslizantes da tela (seção 3.1 do contrato 2.0.0).

    Regra: P-053.1, P-053.2, P-055.3, P-056.3 e A1 — expõe apenas os 4 parâmetros vigentes da
    Política Mín/Máx, sem parâmetros revogados.
    """
    return InventoryConfigData(
        historyWindowDays=RangeParameterConfig(
            default=UI_HISTORY_WINDOW_DAYS_DEFAULT,
            min=UI_HISTORY_WINDOW_DAYS_MIN,
            max=UI_HISTORY_WINDOW_DAYS_MAX,
            step=UI_HISTORY_WINDOW_DAYS_STEP,
        ),
        leadTimeDays=RangeParameterConfig(
            default=UI_LEAD_TIME_DAYS_DEFAULT,
            min=UI_LEAD_TIME_DAYS_MIN,
            max=UI_LEAD_TIME_DAYS_MAX,
            step=UI_LEAD_TIME_DAYS_STEP,
        ),
        minCoverageDays=RangeParameterConfig(
            default=UI_MIN_COVERAGE_DAYS_DEFAULT,
            min=UI_MIN_COVERAGE_DAYS_MIN,
            max=UI_MIN_COVERAGE_DAYS_MAX,
            step=UI_MIN_COVERAGE_DAYS_STEP,
        ),
        maxCoverageDays=RangeParameterConfig(
            default=UI_MAX_COVERAGE_DAYS_DEFAULT,
            min=UI_MAX_COVERAGE_DAYS_MIN,
            max=UI_MAX_COVERAGE_DAYS_MAX,
            step=UI_MAX_COVERAGE_DAYS_STEP,
        ),
    )


def get_inventory_catalog() -> pd.DataFrame:
    """Retorna o catálogo oficial de produtos da Fitoherb com cache thread-safe."""
    if "catalog_df" in _INVENTORY_CACHE:
        return _INVENTORY_CACHE["catalog_df"]

    with _INVENTORY_LOCK:
        if "catalog_df" in _INVENTORY_CACHE:
            return _INVENTORY_CACHE["catalog_df"]

        try:
            from src.modules.pricing.service.pricing_service import _DATA_CACHE

            if "catalog_df" in _DATA_CACHE:
                _INVENTORY_CACHE["catalog_df"] = _DATA_CACHE["catalog_df"]
                return _INVENTORY_CACHE["catalog_df"]
        except Exception:
            pass

        logger.info("Carregando catálogo oficial de produtos do banco SQL Server...")
        catalog_df = load_catalog_from_database()
        _INVENTORY_CACHE["catalog_df"] = catalog_df
        return catalog_df


def get_base_inventory_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Recupera o catálogo oficial de produtos e as vendas limpas para cálculo em memória."""
    if "catalog_df" in _INVENTORY_CACHE and "clean_sales" in _INVENTORY_CACHE:
        return _INVENTORY_CACHE["catalog_df"], _INVENTORY_CACHE["clean_sales"]

    with _INVENTORY_LOCK:
        if "catalog_df" in _INVENTORY_CACHE and "clean_sales" in _INVENTORY_CACHE:
            return _INVENTORY_CACHE["catalog_df"], _INVENTORY_CACHE["clean_sales"]

        try:
            from src.modules.pricing.service.pricing_service import _DATA_CACHE

            if "catalog_df" in _DATA_CACHE and "clean_sales" in _DATA_CACHE:
                _INVENTORY_CACHE["catalog_df"] = _DATA_CACHE["catalog_df"]
                _INVENTORY_CACHE["clean_sales"] = _DATA_CACHE["clean_sales"]
                return _INVENTORY_CACHE["catalog_df"], _INVENTORY_CACHE["clean_sales"]
        except Exception:
            pass

        catalog_df = get_inventory_catalog()
        logger.info("Carregando vendas completas para fallback de inventário...")
        raw_sales = fetch_sales_from_database()
        clean_sales = run_etl_pipeline(raw_sales, catalog_df)

        _INVENTORY_CACHE["catalog_df"] = catalog_df
        _INVENTORY_CACHE["clean_sales"] = clean_sales
        return catalog_df, clean_sales


def get_inventory_velocity(window_days: int) -> pd.DataFrame:
    """Retorna o DataFrame de velocidade de vendas (VMD em precisão integral e receita) na janela.

    Regra: P-041 e P-053.6 (ADR-001, DA-02) — prioriza agregação direta no SQL Server e faz
    fallback analítico em memória quando necessário.
    """
    if window_days in _VELOCITY_CACHE:
        return _VELOCITY_CACHE[window_days]

    with _INVENTORY_LOCK:
        if window_days in _VELOCITY_CACHE:
            return _VELOCITY_CACHE[window_days]

        if "clean_sales" in _INVENTORY_CACHE:
            clean_sales = _INVENTORY_CACHE["clean_sales"]
            vel_df = calculate_sales_velocity(clean_sales, window_days=window_days)
            _VELOCITY_CACHE[window_days] = vel_df
            return vel_df

        try:
            logger.info(
                "Executando agregação direta de velocidade no SQL Server para %s dias...",
                window_days,
            )
            vel_df = fetch_sales_velocity_from_database(window_days=window_days)
            if not vel_df.empty:
                _VELOCITY_CACHE[window_days] = vel_df
                return vel_df
        except Exception as exc:
            logger.warning(
                "Agregação direta no banco indisponível (%s). Utilizando fallback em memória...",
                exc,
            )

        _, clean_sales = get_base_inventory_data()
        logger.info("Calculando velocidade de vendas em memória para janela de %s dias...", window_days)
        vel_df = calculate_sales_velocity(clean_sales, window_days=window_days)
        _VELOCITY_CACHE[window_days] = vel_df
        return vel_df


def get_cached_velocity(window_days: int) -> pd.DataFrame:
    """Mantém compatibilidade retroativa delegando para `get_inventory_velocity`."""
    return get_inventory_velocity(window_days)


def get_inventory_suppliers() -> List[Dict[str, Any]]:
    """Retorna os fornecedores com contagem de SKUs ativos, iniciada por `TODOS`.

    Regra: P-057 — SKUs sem estoque e sem venda na janela padrão não entram na contagem, para
    que o total do seletor coincida com a lista exibida na tela.
    """
    catalog_df = normalize_product_catalog(get_inventory_catalog())
    velocity_df = get_inventory_velocity(UI_HISTORY_WINDOW_DAYS_DEFAULT)
    sold_skus = set(velocity_df.index[velocity_df["vmd"] > 0]) if not velocity_df.empty else set()
    is_active = (catalog_df["estoque"] > 0) | catalog_df["codigo"].isin(sold_skus)
    active_df = catalog_df[is_active]

    counts = active_df["fornecedor"].astype(str).str.strip().value_counts()
    suppliers: List[Dict[str, Any]] = [
        {
            "fornecedor": "TODOS",
            "nome": "Todos os Fornecedores",
            "totalSkus": int(len(active_df)),
        }
    ]
    for supplier_name, count in counts.items():
        if not supplier_name:
            continue
        suppliers.append(
            {
                "fornecedor": supplier_name.upper(),
                "nome": supplier_name.title(),
                "totalSkus": int(count),
            }
        )
    return suppliers


def execute_inventory_prediction(
    request: InventoryPredictRequest,
) -> Tuple[Dict[str, Any], float]:
    """Executa o cálculo de previsão de estoque e compras pela Política Mín/Máx.

    Regra: P-047.1, P-053 a P-056 (ADR-001, DA-08 e DA-10).
    Normaliza e filtra o catálogo por fornecedor mantendo a Curva ABC global calculada sobre
    o DataFrame de velocidade completo, executa o motor Mín/Máx e anexa o eco `politica`.

    Args:
        request: Parâmetros validados da requisição.

    Returns:
        Tupla `(data_dict, elapsed_ms)` onde `data_dict` contém `politica`, `kpis` e `produtos`.
    """
    start_time = time.perf_counter()
    policy = to_replenishment_policy(request)
    catalog_df = prepare_product_catalog(get_inventory_catalog(), request.fornecedor)
    velocity_df = get_inventory_velocity(request.historyWindowDays)

    engine_result = calculate_inventory_replenishment(
        catalog_df=catalog_df,
        velocity_df=velocity_df,
        policy=policy,
    )
    data = {
        "politica": build_policy_echo(request),
        "kpis": engine_result["kpis"],
        "produtos": engine_result["produtos"],
    }
    elapsed_ms = round((time.perf_counter() - start_time) * MILLISECONDS_PER_SECOND, EXECUTION_TIME_DECIMALS)
    return data, elapsed_ms


def generate_inventory_csv(request: InventoryPredictRequest) -> str:
    """Gera o conteúdo CSV do plano de compras com as 17 colunas da Política Mín/Máx.

    Regra: P-056.5 e P-056.6 (seção 6.2 do contrato 2.0.0) — reutiliza `execute_inventory_prediction`
    para garantir paridade integral com `/predict` e preserva o cabeçalho mesmo quando a lista de
    produtos está vazia.
    """
    result, _ = execute_inventory_prediction(request)
    produtos = result["produtos"]

    df_export = pd.DataFrame(produtos, columns=list(INVENTORY_CSV_COLUMNS)).rename(
        columns=INVENTORY_CSV_COLUMNS
    )

    output = io.StringIO()
    output.write(CSV_UTF8_BOM)
    df_export.to_csv(
        output,
        sep=CSV_FIELD_SEPARATOR,
        index=False,
        decimal=CSV_DECIMAL_SEPARATOR,
    )
    return output.getvalue()


def _sanitize_supplier_slug(fornecedor: Optional[str]) -> str:
    """Converte o nome do fornecedor em um slug seguro (`[a-z0-9_]`) ou vazio quando sem filtro."""
    if fornecedor is None:
        return ""

    normalized = fornecedor.strip().upper()
    if normalized in ALL_SUPPLIERS_TOKENS:
        return ""

    raw_slug = SUPPLIER_SLUG_SANITIZE_PATTERN.sub("_", normalized.lower())
    return SUPPLIER_SLUG_COLLAPSE_PATTERN.sub("_", raw_slug).strip("_")


def build_csv_filename(
    fornecedor: Optional[str],
    generated_at: Optional[datetime] = None,
) -> str:
    """Monta o nome de arquivo seguro do CSV do plano de compras.

    Regra: ADR-001 (DA-11) e seção 6.2 do contrato 2.0.0 — sanitiza o fornecedor para conter
    exclusivamente `[a-z0-9_]` no header `Content-Disposition`, prevenindo injeção de cabeçalho.

    Args:
        fornecedor: Filtro de fornecedor recebido na requisição (ou None/TODOS/ALL).
        generated_at: Instante opcional para geração determinística em testes.

    Returns:
        Nome de arquivo no formato `fitoherb_plano_compras[_<slug>]_<AAAAMMDD_HHMMSS>.csv`.
    """
    timestamp_str = (generated_at or datetime.now(timezone.utc)).strftime(CSV_TIMESTAMP_FORMAT)
    supplier_slug = _sanitize_supplier_slug(fornecedor)
    supplier_part = f"_{supplier_slug}" if supplier_slug else ""
    return f"{CSV_FILENAME_PREFIX}{supplier_part}_{timestamp_str}.csv"
