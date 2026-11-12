"""
Testes da Curadoria das Sugestões (P-094): sem variante do produto de origem, uma sugestão por linha
de produto, prioridade para o mesmo fornecedor e similares e só as `MAX_RECOMMENDATIONS` principais.

Contexto: na base real, a maioria das linhas era a mesma linha do fornecedor em outro sabor, aroma ou
tamanho (ex.: WHEY 100% PURE CHOC sugerido para quem compra WHEY 100% PURE BAUN) — reposição de mix,
não cross-sell — e as listas passavam de 100 itens.
"""
from src.modules.analytics.domain.cross_sell import CatalogEntry, UsefulRule
from src.modules.analytics.domain.recommendation_curation import (
    MAX_RECOMMENDATIONS,
    OTHER_PRODUCT_TIER,
    SAME_SUPPLIER_TIER,
    SIMILAR_PRODUCT_TIER,
    priority_tier,
    curate,
    is_variant,
    product_line_key,
)


def entry(code, description, supplier="INTEGRALMEDICA "):
    return CatalogEntry(code=code, description=description, supplier=supplier, stock=10, price=10.0,
                        unit_cost=5.0, is_cost_estimated=False)


def rule(antecedent, consequent):
    return UsefulRule(antecedent=antecedent, consequent=consequent, support=0.01, confidence=0.3, lift=5.0,
                      pair_orders=50, antecedent_orders=150)


# ------------------------------------------------------------------ nome-base da linha

def test_line_key_uses_supplier_and_first_meaningful_word():
    assert product_line_key(entry(1, "WHEY 100% PURE 900G CHOC SACO")) == ("INTEGRALMEDICA", "WHEY")
    assert product_line_key(entry(2, "PASTA DE AMENDOIM CROCANTE 1KG", "POWER ONE")) == ("POWER ONE", "PASTA")
    assert product_line_key(entry(3, "Óleo Essencial de Lavanda 10ml", "NATIVE")) == ("NATIVE", "OLEO")


def test_line_key_ignores_connectors_symbols_and_sizes():
    a = entry(1, "CURCUMA + ORA PRO NOBIS + GENGIBRE", "4ELEMENTOS")
    assert product_line_key(a) == ("4ELEMENTOS", "CURCUMA")
    assert product_line_key(entry(2, "CREATINA 300G", "MAX")) == ("MAX", "CREATINA")


# ------------------------------------------------------------------ variante (P-094.1)

def test_flavor_and_size_of_same_line_are_variants():
    assert is_variant(entry(1, "WHEY 100% PURE 900G BAUN SACO"), entry(2, "WHEY 100% PURE 900G CHOC SACO"))
    assert is_variant(entry(1, "CREATINA 300G", "MAX"), entry(2, "CREATINA 150G", "MAX"))
    assert is_variant(entry(1, "CRISP BAR CREME DE COCO 12UN"), entry(2, "CRISP BAR DUO CRUNCH 12UN"))
    assert is_variant(entry(1, "ARGILA VERDE 500G", "ARGILA & CIA"), entry(2, "ARGILA BRANCA 500G", "ARGILA & CIA"))
    assert is_variant(entry(1, "BALA GENGIBRE SUAVE 50GR", "ARDRAK"), entry(2, "BALAS GENGIBRE MACA 50G", "ARDRAK"))


def test_same_line_from_other_supplier_is_not_variant():
    assert not is_variant(entry(1, "CREATINA 300G", "MAX"), entry(2, "CREATINA 300G", "GROWTH"))


def test_different_products_of_same_supplier_are_not_variants():
    assert not is_variant(entry(1, "GINKGO BILOBA 500MG", "4ELEMENTOS"), entry(2, "CHA VERDE 60 CAPS", "4ELEMENTOS"))


# ------------------------------------------------------------------ curadoria (P-094.1 a P-094.3)

def test_curate_drops_variants_of_the_source_product():
    catalog = {1: entry(1, "WHEY 100% PURE BAUN"), 2: entry(2, "WHEY 100% PURE CHOC"),
               3: entry(3, "COQUETELEIRA 600ML")}
    items = [rule(1, 2), rule(1, 3)]

    kept = curate(items, catalog, rule_of=lambda item: item)

    assert [item.consequent for item in kept] == [3]


def test_curate_keeps_only_the_best_ranked_item_of_each_line():
    catalog = {1: entry(1, "PRE TREINO X"), 2: entry(2, "CRISP BAR COCO"), 3: entry(3, "CRISP BAR AVELA"),
               4: entry(4, "COQUETELEIRA 600ML")}
    items = [rule(1, 2), rule(1, 3), rule(1, 4)]

    kept = curate(items, catalog, rule_of=lambda item: item)

    assert [item.consequent for item in kept] == [2, 4]


def test_curate_keeps_the_input_order_and_caps_the_list():
    catalog = {0: entry(0, "ORIGEM", "S0")}
    catalog.update({code: entry(code, f"LINHA{chr(64 + code)} X", f"FORNECEDOR {code}") for code in range(1, 30)})
    items = [rule(0, code) for code in range(1, 30)]

    kept = curate(items, catalog, rule_of=lambda item: item)

    assert len(kept) == MAX_RECOMMENDATIONS == 10
    assert [item.consequent for item in kept] == list(range(1, 11))


def test_customer_items_compare_against_their_own_main_antecedent():
    """No modo cliente cada item tem a própria regra principal: a variante é medida contra ela."""
    catalog = {1: entry(1, "WHEY 100% PURE BAUN"), 2: entry(2, "WHEY 100% PURE CHOC"),
               5: entry(5, "PASTA DE AMENDOIM CROCANTE", "P1"), 6: entry(6, "COQUETELEIRA", "P2")}
    items = [("a", rule(1, 2)), ("b", rule(5, 6))]

    kept = curate(items, catalog, rule_of=lambda item: item[1])

    assert [label for label, _ in kept] == ["b"]


def test_curate_skips_items_whose_antecedent_left_the_catalog_check():
    """Antecedente fora do catálogo não impede a sugestão (a comparação de variante é só pulada)."""
    catalog = {3: entry(3, "COQUETELEIRA 600ML")}
    kept = curate([rule(99, 3)], catalog, rule_of=lambda item: item)
    assert [item.consequent for item in kept] == [3]



# ------------------------------------------------------------------ priorização (P-094.2)

def test_priority_tier_same_supplier_then_similar_then_other():
    source = entry(1, "OLEO DE RICINO PURO 100ML", "FARMAX")
    assert priority_tier(source, entry(2, "SAL AMARGO 30G", "FARMAX")) == SAME_SUPPLIER_TIER
    assert priority_tier(source, entry(3, "OLEO DE SEMENTE DE ABOBORA 250ML", "PAZZE")) == SIMILAR_PRODUCT_TIER
    assert priority_tier(source, entry(4, "ZINCO 60 COMPR", "TIARAJU")) == OTHER_PRODUCT_TIER
    assert priority_tier(None, entry(4, "ZINCO 60 COMPR", "TIARAJU")) == OTHER_PRODUCT_TIER


def test_curate_puts_same_supplier_first_then_similar_keeping_rank_inside_each_tier():
    catalog = {
        0: entry(0, "OLEO DE RICINO PURO 100ML", "FARMAX"),
        1: entry(1, "ZINCO 60 COMPR", "TIARAJU"),               # outro (melhor ranking)
        2: entry(2, "OLEO DE ABACATE 250ML", "PAZZE"),          # similar
        3: entry(3, "SAL AMARGO 30G", "FARMAX"),                # mesmo fornecedor
        4: entry(4, "VITAMINA D3 60 CAPS", "TIARAJU"),          # outro
        5: entry(5, "AGUA DE ROSAS 100ML", "FARMAX"),           # mesmo fornecedor
    }
    items = [rule(0, code) for code in (1, 2, 3, 4, 5)]

    kept = curate(items, catalog, rule_of=lambda item: item)

    assert [item.consequent for item in kept] == [3, 5, 2, 1, 4]


def test_customer_mode_prioritizes_against_each_item_main_antecedent():
    catalog = {
        10: entry(10, "COMPLEX B 60 COMPR", "TIARAJU"), 11: entry(11, "OMEGA 3 120 CAPS", "VITAFOR"),
        20: entry(20, "SIMFORT PLUS 60 CAPS", "VITAFOR"), 21: entry(21, "ZINCO 60 COMPR", "TIARAJU"),
    }
    items = [("omega", rule(10, 11)), ("zinco", rule(20, 21)), ("mesmo", rule(10, 21))]

    kept = curate(items, catalog, rule_of=lambda item: item[1])

    assert [label for label, _ in kept] == ["mesmo", "omega"]  # zinco é a mesma linha de "mesmo" (P-094.3)


def test_products_without_supplier_are_not_same_supplier_nor_variants():
    """N-1 (reviewer): fornecedor vazio é desconhecido, não "o mesmo fornecedor"."""
    source = entry(1, "ARGILA VERDE 500G", "  ")
    candidate = entry(2, "ARGILA BRANCA 500G", "")
    assert not is_variant(source, candidate)
    assert priority_tier(source, candidate) == SIMILAR_PRODUCT_TIER  # ainda compartilha "ARGILA"
