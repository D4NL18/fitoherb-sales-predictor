"""
Normalização e predicados de busca para produtos e fornecedores (P-081.1, ADR-003 DA-10).
"""
import re
import unicodedata

MIN_DIGITS_QUERY_LENGTH: int = 1
MIN_TEXT_QUERY_LENGTH: int = 2
MAX_QUERY_LENGTH: int = 60

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """
    Normaliza texto com decomposição NFKD, remove marcas diacríticas (acentos),
    converte para minúsculas e colapsa múltiplos espaços em branco.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    collapsed = _WHITESPACE_PATTERN.sub(" ", without_accents).strip().lower()
    return collapsed


def is_valid_search_query(query: str) -> bool:
    """
    Valida tamanho da query de busca (P-081.1).
    - 1 a 60 caracteres se composta apenas por dígitos.
    - 2 a 60 caracteres nos demais casos (texto).
    """
    if not query:
        return False
    trimmed = query.strip()
    length = len(trimmed)
    if length == 0 or length > MAX_QUERY_LENGTH:
        return False

    if trimmed.isdigit():
        return length >= MIN_DIGITS_QUERY_LENGTH
    return length >= MIN_TEXT_QUERY_LENGTH


def matches_product(query: str, sku: int, normalized_description: str) -> bool:
    """
    Predicado de correspondência para produto:
    - Se a query for apenas dígitos: código igual ou prefixo do código.
    - Se for texto: descrição normalizada contém a query normalizada.
    """
    trimmed = query.strip()
    if trimmed.isdigit():
        str_sku = str(sku)
        return str_sku == trimmed or str_sku.startswith(trimmed)

    normalized_q = normalize_text(trimmed)
    if not normalized_q:
        return True
    return normalized_q in normalized_description


def matches_supplier(query: str, normalized_supplier_name: str) -> bool:
    """
    Predicado de correspondência para fornecedor (nome contém a query, inclusive dígitos).
    """
    normalized_q = normalize_text(query)
    if not normalized_q:
        return True
    return normalized_q in normalized_supplier_name
