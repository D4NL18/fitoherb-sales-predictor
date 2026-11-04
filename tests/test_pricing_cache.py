"""
Testes do cache em memória do módulo de Pricing.
Garante a carga de voo único: no cold start do Cloud Run, o pré-aquecimento e a primeira
requisição concorrentes não podem carregar a base duas vezes (pico de memória -> OOM -> 503).
"""
import threading
import time

from src.modules.pricing.service import pricing_service

CONCURRENT_CALLERS = 5
SIMULATED_LOAD_SECONDS = 0.2


def test_concurrent_calls_load_base_data_only_once(monkeypatch):
    """Chamadas simultâneas com cache vazio disparam uma única carga e todas recebem o mesmo cache."""
    load_calls = []

    def fake_load():
        load_calls.append(threading.get_ident())
        time.sleep(SIMULATED_LOAD_SECONDS)
        pricing_service._DATA_CACHE["rules_df"] = "loaded"

    monkeypatch.setattr(pricing_service, "_DATA_CACHE", {})
    monkeypatch.setattr(pricing_service, "_load_base_data_into_cache", fake_load)

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(pricing_service.get_cached_base_data()))
        for _ in range(CONCURRENT_CALLERS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(load_calls) == 1
    assert len(results) == CONCURRENT_CALLERS
    assert all(result["rules_df"] == "loaded" for result in results)


def test_force_reload_always_reloads(monkeypatch):
    """force_reload=True (rota /sync-db) recarrega mesmo com o cache já preenchido."""
    load_calls = []
    monkeypatch.setattr(pricing_service, "_DATA_CACHE", {"rules_df": "old"})
    monkeypatch.setattr(pricing_service, "_load_base_data_into_cache", lambda: load_calls.append(1))

    pricing_service.get_cached_base_data(force_reload=True)

    assert load_calls == [1]
