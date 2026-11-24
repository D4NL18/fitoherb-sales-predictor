"""T-7.2.1: pacote enviado ao LLM por lista branca (LGPD-TIA-03/04/05/06, P-179, P-184)."""
import json

from tests.trend_insights.helpers import canonical_evidence, make_evidence, mod

CUSTOMER = 987654321
FORBIDDEN_KEYS = {"customer", "customer_code", "cliente", "codcliente", "cod_cliente", "nome", "cpf", "cnpj",
                  "email", "ultimo_custo", "unit_cost", "custo_unitario", "pc.ultimo custo"}


def _payload(**over):
    return mod("llm.evidence_payload").build_llm_payload(make_evidence(**over))


def _all_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k).lower()
            yield from _all_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _all_keys(v)


def test_payload_is_json_and_has_no_forbidden_keys_or_customer_values():
    base = canonical_evidence()
    base["cascata"][1]["itens"][0].update({"customer_code": CUSTOMER, "ultimo_custo": 7.3, "cpf": "123", "email": "a@b"})
    base["afins"][0]["codCliente"] = CUSTOMER
    ev = mod("domain.evidence").EvidencePackage.from_mapping(base, data_referencia=__import__("datetime").date(2026, 11, 9))
    text = mod("llm.evidence_payload").build_llm_payload(ev)
    assert str(CUSTOMER) not in text and "ultimo" not in text.lower()
    assert not (set(_all_keys(json.loads(text))) & FORBIDDEN_KEYS)


def test_small_client_counts_become_less_than_three():
    base = canonical_evidence()
    base["cascata"][1]["itens"][0]["clientes_migrados"] = 1
    ev = mod("domain.evidence").EvidencePackage.from_mapping(base, data_referencia=__import__("datetime").date(2026, 11, 9))
    data = json.loads(mod("llm.evidence_payload").build_llm_payload(ev))
    assert '"<3"' in json.dumps(data)
    assert not any(isinstance(v, int) and k.startswith("clientes") and v < 3 for k, v in _pairs(data))


def _pairs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k), v
            yield from _pairs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _pairs(v)


def test_gallery_description_is_sanitized_and_truncated():
    dirty = "<b>Cha</b> <script>x</script> veja https://evil.example/x " + "z" * 900 + " ```fim```"
    text = _payload(produto={"descricao_galeria": dirty})
    assert "<b>" not in text and "<script" not in text and "https://evil" not in text and "```" not in text
    gallery = json.loads(text)
    flat = json.dumps(gallery)
    assert "z" * 501 not in flat


def test_payload_respects_8000_chars_even_with_many_affines_and_pairs():
    base = canonical_evidence()
    base["afins"] = [{**base["afins"][0], "sku": 6000 + i, "descricao": "D" * 60} for i in range(25)]
    base["cascata"][1]["itens"] = [{**base["cascata"][1]["itens"][0], "sku": 7000 + i, "descricao": "E" * 80} for i in range(20)]
    ev = mod("domain.evidence").EvidencePackage.from_mapping(base, data_referencia=__import__("datetime").date(2026, 11, 9))
    text = mod("llm.evidence_payload").build_llm_payload(ev)
    assert len(text) <= 8000
    assert len(json.loads(text)["afins"]) <= 10


def test_payload_has_no_numeric_substitution_markers_and_is_deterministic():
    text = _payload()
    assert "{{" not in text and text == _payload()
