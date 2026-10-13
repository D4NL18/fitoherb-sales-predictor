"""
Middleware ASGI de Autenticação HTTP Basic para ambiente de Produção (Regra P-033).
Parte do módulo core de segurança.
"""
import base64
import os
import secrets
from fastapi import Response


class HTTPBasicAuthASGIMiddleware:
    """
    Middleware ASGI de Autenticação HTTP Basic para ambiente de Produção (Regra P-033).
    - Em ambiente local (AUTH_REQUIRED=false ou ENVIRONMENT!=production), o acesso é livre.
    - Em produção, solicita login e senha nativos pelo navegador (WWW-Authenticate: Basic).
    - As credenciais são obtidas exclusivamente via variáveis de ambiente AUTH_USERNAME e AUTH_PASSWORD.
    - Suporta streaming SSE, arquivos estáticos e requisições OPTIONS pré-voo de CORS.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Requisições OPTIONS (CORS preflight) sempre são liberadas
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        auth_required = (
            os.getenv("AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")
            or os.getenv("ENVIRONMENT", "").lower() == "production"
        )
        if not auth_required:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("latin1")

        authorized = False
        if auth_header.startswith("Basic "):
            try:
                encoded = auth_header.split(" ", 1)[1]
                decoded = base64.b64decode(encoded).decode("utf-8")
                username, password = decoded.split(":", 1)
                expected_user = os.getenv("AUTH_USERNAME", "")
                expected_pass = os.getenv("AUTH_PASSWORD", "")
                if expected_user and expected_pass:
                    authorized = (
                        secrets.compare_digest(username, expected_user)
                        and secrets.compare_digest(password, expected_pass)
                    )
            except Exception:
                authorized = False

        if not authorized:
            response = Response(
                content="Autenticação necessária. Insira o usuário e senha da Fitoherb.",
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Fitoherb Pricing Predictor"',
                    "Access-Control-Expose-Headers": "WWW-Authenticate"
                },
                media_type="text/plain; charset=utf-8",
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
