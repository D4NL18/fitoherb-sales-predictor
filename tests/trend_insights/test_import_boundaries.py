"""T-7.1.7 / ADR-009 DA-01 / ADR-003: isolamento de imports por camada (analise estatica via AST)."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "modules"
TI = ROOT / "trend_insights"
OTHER_MODULES = ("src.modules.sales_trend", "src.modules.analytics")


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def _files(sub: str):
    assert TI.is_dir(), "src/modules/trend_insights ainda nao existe"
    base = TI / sub
    assert base.is_dir(), f"trend_insights/{sub} ainda nao existe"
    return sorted(p for p in base.rglob("*.py"))


def _bad(imports, prefixes):
    return [i for i in imports if any(i == p or i.startswith(p + ".") for p in prefixes)]


def _is_pure_domain_of_other(name: str) -> bool:
    return any(name == m + ".domain" or name.startswith(m + ".domain.") for m in OTHER_MODULES)


def test_module_layout_exists():
    for sub in ("domain", "adapters", "service", "store", "llm", "api"):
        assert (TI / sub).is_dir(), sub


def test_domain_is_pure():
    for path in _files("domain"):
        imps = list(_imports(path))
        assert not _bad(imps, ["fastapi", "pyodbc", "google", "src.core"]), path
        for name in imps:
            touches_other = any(name == m or name.startswith(m + ".") for m in OTHER_MODULES)
            assert not touches_other or _is_pure_domain_of_other(name), (path, name)


def test_llm_package_only_gemini_client_has_io():
    for path in _files("llm"):
        imps = list(_imports(path))
        if path.name == "gemini_client.py":
            continue
        assert not _bad(imps, ["fastapi", "pyodbc", "google", "src.core"]), path
        assert not _bad(imps, list(OTHER_MODULES)), path


def test_only_adapters_import_sales_trend_and_analytics():
    for sub in ("service", "store", "llm", "api"):
        for path in _files(sub):
            assert not _bad(_imports(path), list(OTHER_MODULES)), path


def test_sdks_and_db_only_where_allowed():
    for sub in ("service", "store", "api", "adapters"):
        for path in _files(sub):
            assert not _bad(_imports(path), ["google", "pyodbc"]), path
    for path in _files("service") + _files("llm"):
        assert not _bad(_imports(path), ["fastapi"]), path


def test_api_does_not_import_adapters_store_or_llm_client_impl():
    for path in _files("api"):
        assert not _bad(
            _imports(path),
            ["src.modules.trend_insights.adapters", "src.modules.trend_insights.store",
             "src.modules.trend_insights.llm.gemini_client"],
        ), path


def test_service_does_not_import_adapters():
    for path in _files("service"):
        assert not _bad(_imports(path), ["src.modules.trend_insights.adapters"]), path


@pytest.mark.parametrize("module_dir", ["sales_trend", "analytics"])
def test_older_modules_do_not_import_trend_insights(module_dir):
    for path in (ROOT / module_dir).rglob("*.py"):
        assert not _bad(_imports(path), ["src.modules.trend_insights"]), path


def test_sales_trend_does_not_import_analytics():
    for path in (ROOT / "sales_trend").rglob("*.py"):
        assert not _bad(_imports(path), ["src.modules.analytics"]), path
