"""
Testes Unitários — Índice Incremental de Afinidade Semântica de Produtos (F6 v2.1 + Produto Novo).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.modules.analytics.domain import cannibalization_report as can_dom
from src.modules.analytics.domain import product_affinity as aff_dom
from src.modules.analytics.service import product_affinity_service as aff_svc


def _sample_catalog() -> Dict[str, Dict[str, Any]]:
    return {
        "770019": {
            "sku": "770019",
            "description": "CREATINA 300G",
            "category": "LINHA MAX TITANIUM",
            "supplier": "MAX TITANIUM",
            "active": True,
            "current_price": 45.0,
            "last_cost": 25.0,
            "current_stock": 100,
        },
        "111940": {
            "sku": "111940",
            "description": "CREATINA 300 GRS",
            "category": "LINHA INTEGRALMEDICA",
            "supplier": "INTEGRALMEDICA",
            "active": True,
            "current_price": 53.9,
            "last_cost": 30.0,
            "current_stock": 80,
        },
        "112246": {
            "sku": "112246",
            "description": "CREATINA HARDCORE 500G POTE",
            "category": "LINHA INTEGRALMEDICA",
            "supplier": "INTEGRALMEDICA",
            "active": True,
            "current_price": 69.9,
            "last_cost": 40.0,
            "current_stock": 60,
        },
        "770999": {
            "sku": "770999",
            "description": "WHEY 100% HD 900G CHOCOLATE REFIL",
            "category": "LINHA MAX TITANIUM",
            "supplier": "MAX TITANIUM",
            "active": True,
            "current_price": 120.0,
            "last_cost": 70.0,
            "current_stock": 40,
        },
    }


def _sample_gallery() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Creatina 300g",
            "description": "Creatina monohidratada pura para aumento de forca muscular e desempenho fisico.",
            "category_name": "Suplementos",
            "supplier_name": "Max Titanium",
            "slug": "creatina-300g-max-titanium",
            "flavours": [],
            "presentation": ["Pote 300g"],
        },
        {
            "name": "Creatina 300g Hardcore",
            "description": "Creatina monohidratada para potencia, explosao e ganho de forca muscular.",
            "category_name": "Suplementos",
            "supplier_name": "Integralmedica",
            "slug": "creatina-300g-integralmedica",
            "flavours": [],
            "presentation": ["Pote 300g"],
        },
        {
            "name": "Creatina Hardcore 500g Pote",
            "description": "Creatina monohidratada em pote economico de 500g para forca e performance.",
            "category_name": "Suplementos",
            "supplier_name": "Integralmedica",
            "slug": "creatina-500g-integralmedica",
            "flavours": [],
            "presentation": ["Pote 500g"],
        },
        {
            "name": "Whey 100% HD 900g Chocolate Refil",
            "description": "Proteina concentrada do soro do leite com BCAA para recuperacao muscular.",
            "category_name": "Suplementos",
            "supplier_name": "Max Titanium",
            "slug": "whey-100-hd-max-titanium",
            "flavours": ["Chocolate"],
            "presentation": ["Refil 900g"],
        },
    ]


def test_gallery_matching_and_supplier_agnostic_affinity_ranking(tmp_path: Path):
    """Creatina Max Titanium deve ter maior afinidade com Creatinas da Integralmedica do que com Whey Max Titanium."""
    index_path = tmp_path / "affinity.json"
    aff_svc.reset_product_affinity_memory_cache()

    summary = aff_svc.sync_product_affinity_index(
        index_path=index_path,
        catalog_loader=_sample_catalog,
        gallery_loader=_sample_gallery,
    )
    assert summary["recomputed"] is True
    assert summary["total_active_skus"] == 4
    assert summary["gallery_matched_skus"] == 4

    result = aff_svc.get_product_affinities("770019", top_k=10, index_path=index_path)
    assert result is not None
    affs = result["affinities"]
    assert len(affs) >= 2
    # Ordem estritamente decrescente de score
    scores = [a["affinityScore"] for a in affs]
    assert scores == sorted(scores, reverse=True)
    # Top 2 devem ser as creatinas da Integralmedica (outro fornecedor), acima do Whey da Max Titanium
    top_two_skus = {affs[0]["sku"], affs[1]["sku"]}
    assert top_two_skus == {"111940", "112246"}
    assert affs[0]["sameSupplier"] is False


def test_incremental_sync_only_recomputes_on_changes_and_removes_deactivated(tmp_path: Path):
    """Cron incremental: pula recálculo sem mudanças; ao adicionar/alterar/desativar, remove inativos."""
    index_path = tmp_path / "affinity_inc.json"
    aff_svc.reset_product_affinity_memory_cache()

    # 1) Carga inicial
    s1 = aff_svc.sync_product_affinity_index(
        index_path=index_path,
        catalog_loader=_sample_catalog,
        gallery_loader=_sample_gallery,
    )
    assert s1["recomputed"] is True
    assert s1["added_count"] == 4
    assert s1["removed_count"] == 0

    # 2) Segunda execução sem mudanças -> não recalcula
    s2 = aff_svc.sync_product_affinity_index(
        index_path=index_path,
        catalog_loader=_sample_catalog,
        gallery_loader=_sample_gallery,
    )
    assert s2["recomputed"] is False
    assert s2["unchanged_count"] == 4
    assert s2["added_count"] == 0
    assert s2["updated_count"] == 0
    assert s2["removed_count"] == 0

    # 3) Terceira execução: desativa 112246, altera 111940, adiciona 660073 (Vitafor)
    def _updated_catalog():
        cat = _sample_catalog()
        del cat["112246"]
        cat["111940"]["description"] = "CREATINA MONOHIDRATADA 300 GRS NOVA"
        cat["660073"] = {
            "sku": "660073",
            "description": "CREATINA 300G",
            "category": "LINHA VITAFOR",
            "supplier": "VITAFOR",
            "active": True,
            "current_price": 70.0,
            "last_cost": 40.0,
            "current_stock": 50,
        }
        return cat

    s3 = aff_svc.sync_product_affinity_index(
        index_path=index_path,
        catalog_loader=_updated_catalog,
        gallery_loader=_sample_gallery,
    )
    assert s3["recomputed"] is True
    assert s3["added_count"] == 1
    assert s3["removed_count"] == 1
    assert s3["total_active_skus"] == 4

    # SKU desativado não pode mais existir nem ser sugerido em afinidades
    assert aff_svc.get_product_affinities("112246", index_path=index_path) is None
    res_770019 = aff_svc.get_product_affinities("770019", index_path=index_path)
    assert res_770019 is not None
    neighbor_skus = {item["sku"] for item in res_770019["affinities"]}
    assert "112246" not in neighbor_skus
    assert "660073" in neighbor_skus


def test_find_similar_for_new_product_cold_start(tmp_path: Path):
    """Caso de uso Produto Novo: encontra creatinas ativas de qualquer marca para um SKU candidato novo."""
    index_path = tmp_path / "affinity_new.json"
    aff_svc.reset_product_affinity_memory_cache()
    aff_svc.sync_product_affinity_index(
        index_path=index_path,
        catalog_loader=_sample_catalog,
        gallery_loader=_sample_gallery,
    )

    matches = aff_svc.find_similar_for_new_product(
        name="Creatina Monohidratada 500g",
        description="Suplemento de creatina pura para forca muscular e desempenho esportivo.",
        category="Suplementos",
        top_k=3,
        index_path=index_path,
    )
    assert len(matches) >= 2
    assert matches[0]["sku"] in {"770019", "111940", "112246"}
    assert matches[0]["affinityScore"] >= matches[-1]["affinityScore"]


def test_cannibalization_uses_semantic_affinity_across_different_product_names():
    """Dois produtos com nomes diferentes (ex.: Omegafor Plus vs Oleo de Peixe EPA DHA) casam via affinity_map."""
    catalog = {
        "660081": {
            "sku": "660081",
            "description": "OMEGAFOR PLUS 1000MG 120 CAPS",
            "category": "LINHA VITAFOR",
            "supplier": "VITAFOR",
            "active": True,
            "current_price": 90.0,
            "last_cost": 50.0,
            "current_stock": 100,
        },
        "250900": {
            "sku": "250900",
            "description": "OLEO DE PEIXE EPA DHA 120 CAPS",
            "category": "LINHA FLORA NATIVA",
            "supplier": "FLORA NATIVA",
            "active": True,
            "current_price": 60.0,
            "last_cost": 35.0,
            "current_stock": 120,
        },
    }
    affinity_map = {"660081": {"250900": 0.78}, "250900": {"660081": 0.78}}
    rows = [
        {"customer_code": cid, "sku": "660081", "pre_qty": 3, "pre_rev": 300.0, "cur_qty": 0, "cur_rev": 0.0}
        for cid in range(1, 5)
    ] + [
        {"customer_code": cid, "sku": "250900", "pre_qty": 0, "pre_rev": 0.0, "cur_qty": 4, "cur_rev": 240.0}
        for cid in range(1, 5)
    ]

    snapshot = can_dom.compute_directional_migration(rows, catalog, affinity_map=affinity_map)
    report = can_dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3)
    assert len(report.victims) == 1
    assert report.victims[0].sku == "660081"
    assert report.victims[0].top_cannibal.sku == "250900"
    assert report.victims[0].top_cannibal.supplier == "FLORA NATIVA"


def test_seconds_until_next_midnight_calculation():
    ref = datetime(2026, 11, 24, 23, 30, 0)
    assert aff_svc.seconds_until_next_midnight(ref) == pytest.approx(1800.0, abs=1e-3)
