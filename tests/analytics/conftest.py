"""
Fixtures compartilhadas dos testes do módulo Analytics Comercial (Fase 1).

Interface que o Desenvolvedor DEVE expor para estes fixtures funcionarem (decisões do Tester,
registradas em `.agents/docs/STATE_Tester.md`):
- `service/analytics_cache.py`: `reset_cache()` (limpa snapshot, catálogo, flag de carga e duração),
  `_utc_now()` (relógio substituível), `_build_snapshot()` (carga completa, chamada sob o lock).
- `repository/sales_repository.py`: `fetch_order_baskets(cutoff: date) -> DataFrame` e
  `fetch_catalog() -> DataFrame`. Quem os usa deve chamá-los pelo módulo ou importá-los por nome;
  `patch_repository` substitui os dois casos.
Nenhum fixture acessa o banco real.
"""
from __future__ import annotations

import importlib
from typing import Callable, List, Optional, Tuple

import pandas as pd
import pytest

from tests.analytics.fixtures.synthetic_data import FIXED_NOW_UTC

CACHE_MODULE = "src.modules.analytics.service.analytics_cache"
SERVICE_MODULE = "src.modules.analytics.service.analytics_service"
REPOSITORY_MODULE = "src.modules.analytics.repository.sales_repository"


def _import_optional(module_name: str):
    """Importa o módulo se ele já existir (antes da implementação os testes falham no próprio teste)."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


@pytest.fixture(autouse=True)
def reset_analytics_cache():
    """Isola o estado global do cache entre testes (snapshot, catálogo, flag de carga)."""
    cache = _import_optional(CACHE_MODULE)
    if cache is not None:
        cache.reset_cache()
    yield
    if cache is not None:
        cache.reset_cache()


@pytest.fixture
def fixed_clock(monkeypatch):
    """Congela `_utc_now()` do cache em 2026-11-05 15:00 UTC (data de referência 2026-11-05 em UTC-3)."""
    cache = importlib.import_module(CACHE_MODULE)
    monkeypatch.setattr(cache, "_utc_now", lambda: FIXED_NOW_UTC)
    return FIXED_NOW_UTC


class RepositoryCalls:
    """Registro das chamadas ao repositório substituído."""

    def __init__(self) -> None:
        self.order_baskets_cutoffs: List[object] = []
        self.catalog_calls = 0


def patch_repository(
    monkeypatch,
    order_baskets: Optional[pd.DataFrame],
    catalog: Optional[pd.DataFrame],
    order_baskets_error: Optional[Exception] = None,
) -> RepositoryCalls:
    """
    Substitui `fetch_order_baskets` e `fetch_catalog` no repositório e em todo módulo do analytics que
    os tenha importado por nome. `order_baskets=None` faz a função falhar o teste se for chamada.
    """
    calls = RepositoryCalls()

    def fake_fetch_order_baskets(cutoff):
        calls.order_baskets_cutoffs.append(cutoff)
        if order_baskets_error is not None:
            raise order_baskets_error
        if order_baskets is None:
            raise AssertionError("fetch_order_baskets não deveria ser chamado neste cenário")
        return order_baskets.copy()

    def fake_fetch_catalog():
        calls.catalog_calls += 1
        if catalog is None:
            raise AssertionError("fetch_catalog não deveria ser chamado neste cenário")
        return catalog.copy()

    repository = importlib.import_module(REPOSITORY_MODULE)
    monkeypatch.setattr(repository, "fetch_order_baskets", fake_fetch_order_baskets)
    monkeypatch.setattr(repository, "fetch_catalog", fake_fetch_catalog)
    for module_name in (CACHE_MODULE, SERVICE_MODULE):
        module = _import_optional(module_name)
        if module is None:
            continue
        if hasattr(module, "fetch_order_baskets"):
            monkeypatch.setattr(module, "fetch_order_baskets", fake_fetch_order_baskets)
        if hasattr(module, "fetch_catalog"):
            monkeypatch.setattr(module, "fetch_catalog", fake_fetch_catalog)
    return calls


@pytest.fixture
def repository_patcher(monkeypatch) -> Callable[..., RepositoryCalls]:
    """Fábrica de `patch_repository` já ligada ao `monkeypatch` do teste."""

    def _patch(order_baskets, catalog, order_baskets_error=None) -> RepositoryCalls:
        return patch_repository(monkeypatch, order_baskets, catalog, order_baskets_error)

    return _patch


def build_snapshot_from_mass(mass: Tuple[pd.DataFrame, pd.DataFrame]):
    """
    Monta um snapshot real (repositório substituído, relógio fixo) chamando `get_snapshot()` uma vez.
    Usado em fixtures de escopo de módulo para não minerar 10.000 cestas a cada teste.
    """
    cache = importlib.import_module(CACHE_MODULE)
    order_baskets, catalog = mass
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(cache, "_utc_now", lambda: FIXED_NOW_UTC)
        calls = patch_repository(patcher, order_baskets, catalog)
        cache.reset_cache()
        snapshot = cache.get_snapshot()
        cache.reset_cache()
    return snapshot, calls


def install_snapshot(monkeypatch, snapshot) -> None:
    """Publica um snapshot pronto no cache, com o relógio fixo (cache QUENTE) e sem acesso ao banco."""
    cache = importlib.import_module(CACHE_MODULE)
    monkeypatch.setattr(cache, "_utc_now", lambda: FIXED_NOW_UTC)
    monkeypatch.setattr(cache, "_SNAPSHOT", snapshot)
    patch_repository(monkeypatch, None, None)
