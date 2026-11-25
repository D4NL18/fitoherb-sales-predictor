"""
Verificador de token OIDC do Google (unico ponto com `google.oauth2`): confere assinatura, expiracao e audiencia.
Importacao tardia: nada acessa rede nem exige o SDK ao importar o modulo. Qualquer falha vira `ValueError` sem
o texto do token ou da excecao original.
"""
from typing import Any, Mapping


class GoogleOidcVerifier:
    def verify(self, token: str, audience: str) -> Mapping[str, Any]:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            return id_token.verify_oauth2_token(token, google_requests.Request(), audience)
        except Exception:  # a biblioteca levanta tipos variados: todos significam token invalido
            raise ValueError("token OIDC invalido") from None
