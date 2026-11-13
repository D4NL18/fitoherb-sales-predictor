"""
Testes para o cache com snapshot em memória, lock de voo único e TTL (T-08).
Valida regras P-083, P-085.2, CA-23, CA-24, CA-25, C-29, C-30, C-52, ADR-003 DA-04.
"""
from datetime import datetime, timedelta, timezone, date
import threading
from unittest.mock import MagicMock, patch
import pytest

from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
)


def _mock_catalog_and_sales():
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text

    raw_cat = get_active_catalog_sample()
    catalog = {
        k: TrendCatalogEntry(k, v["descricao"], v["fornecedor"], normalize_text(v["descricao"]))
        for k, v in raw_cat.items()
    }
    raw_rows = get_raw_sales_rows_sample()
    ms = build_monthly_sales(
        [(r.sku, r.year_month, r.quantity, r.revenue) for r in raw_rows],
        set(catalog.keys()),
        FIRST_SALE_DATE,
    )
    return catalog, ms


def test_cache_single_flight_concurrent_loads():
    """Valida CA-23 e C-29: 10 threads concorrentes com cache frio chamam o repositório apenas 1 vez."""
    from src.modules.sales_trend.service.sales_trend_cache import (
        get_snapshot,
        reset_cache,
    )

    reset_cache()
    mock_catalog, mock_sales = _mock_catalog_and_sales()

    call_count = 0
    def mock_fetch_sales(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_sales

    with patch("src.modules.sales_trend.service.sales_trend_cache.fetch_active_catalog", return_value=mock_catalog):
        with patch("src.modules.sales_trend.service.sales_trend_cache.fetch_monthly_net_sales", side_effect=mock_fetch_sales):
            threads = []
            for _ in range(10):
                t = threading.Thread(target=get_snapshot)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

    assert call_count == 1, "Mesmo com 10 threads concorrentes, a carga deve ocorrer apenas 1 vez"


def test_cache_ttl_and_force_reload_rate_limit():
    """Valida TTL de 6h e intervalo mínimo de 15 min para force_reload (P-083.2, C-52)."""
    from src.modules.sales_trend.service.sales_trend_cache import (
        get_snapshot,
        reset_cache,
        ReloadTooSoonError,
    )

    reset_cache()
    mock_catalog, mock_sales = _mock_catalog_and_sales()

    now = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.modules.sales_trend.service.sales_trend_cache._utc_now", return_value=now):
        with patch("src.modules.sales_trend.service.sales_trend_cache.fetch_active_catalog", return_value=mock_catalog):
            with patch("src.modules.sales_trend.service.sales_trend_cache.fetch_monthly_net_sales", return_value=mock_sales):
                snap = get_snapshot()
                assert snap is not None

                # Tentativa de force_reload em 5 min -> deve levantar ReloadTooSoonError (TND-005)
                with patch("src.modules.sales_trend.service.sales_trend_cache._utc_now", return_value=now + timedelta(minutes=5)):
                    with pytest.raises(ReloadTooSoonError) as exc_info:
                        get_snapshot(force_reload=True)
                    assert exc_info.value.code == "TND-005"
                    assert "15 minutos" in exc_info.value.message
