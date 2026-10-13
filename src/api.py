"""
API RESTful FastAPI para a Plataforma Fitoherb AI Suite.
Atua como ponto de entrada corporativo e orquestrador de microsserviços/módulos DDD.
Fitoherb Nordeste Distribuidora.
"""
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Carrega .env da raiz do repositório
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

from src.core.auth import HTTPBasicAuthASGIMiddleware
from src.modules.inventory.api.router import inventory_router
from src.modules.pricing.api.router import pricing_router
from src.modules.pricing.api.schemas import (
    AutoTuneData,
    AutoTuneRequest,
    AutoTuneResponse,
    OptimalParams,
    PricingRequest,
    PricingSummary,
    ProductPreview,
)
from src.modules.pricing.service.pricing_service import (
    _DATA_CACHE,
    execute_pricing_computation,
    get_cached_base_data,
    get_cached_etl_data,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa o servidor imediatamente e pré-aquece o cache em segundo plano."""
    import threading
    def _warmup():
        try:
            print("[CACHE] Pré-aquecendo cache de dados analíticos e FP-Growth...", flush=True)
            get_cached_base_data()
            print("[CACHE] Cache pré-aquecido com sucesso! Simulações responderão em < 300ms.", flush=True)
        except Exception as e:
            print(f"[CACHE] Aviso no pré-aquecimento: {e}", flush=True)

    threading.Thread(target=_warmup, daemon=True).start()
    yield


app = FastAPI(
    title="Fitoherb AI Suite API",
    description="Plataforma Integrada de Serviços de Inteligência Artificial para a Fitoherb Nordeste",
    version="1.3.0",
    lifespan=lifespan
)

# Adicionar autenticação HTTP Basic (ativa apenas em produção conforme P-033)
app.add_middleware(HTTPBasicAuthASGIMiddleware)

# Habilitar CORS para o frontend Angular (localhost:4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["WWW-Authenticate"],
)

# Registro Modular de Roteadores (DDD)
app.include_router(pricing_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")


# Montagem do Frontend Angular compilado para Produção (P-033)
_dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "frontend" / "browser"
if _dist_dir.exists():
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from fastapi.responses import FileResponse

    # Monta arquivos estáticos mantendo suporte a SPA
    app.mount("/static", StaticFiles(directory=str(_dist_dir)), name="static_assets")

    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        # Se for uma rota de API que não existe, retorna JSON 404
        if request.url.path.startswith("/api"):
            return Response(content='{"detail":"Not Found"}', status_code=404, media_type="application/json")
        # Para qualquer rota do frontend (ex: /pricing, /inventory), serve o index.html da SPA
        index_file = _dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return Response(content="Not Found", status_code=404)

    # Rota raiz e montagem de arquivos estáticos na raiz com html=True
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="static")



__all__ = [
    "app",
    "get_cached_base_data",
    "get_cached_etl_data",
    "execute_pricing_computation",
    "_DATA_CACHE",
    "PricingRequest",
    "ProductPreview",
    "PricingSummary",
    "AutoTuneRequest",
    "OptimalParams",
    "AutoTuneData",
    "AutoTuneResponse",
]
