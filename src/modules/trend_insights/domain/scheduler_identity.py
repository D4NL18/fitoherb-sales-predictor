"""
Regra pura de quem pode chamar a rota interna de sincronizacao (ADR-009 DA-06, LGPD-TIA-14): o token OIDC do
Cloud Scheduler so vale se a audiencia for a configurada, o e-mail for o da conta de servico chamadora e o
e-mail estiver verificado. A assinatura e a expiracao sao checadas pelo verificador (biblioteca do Google).
"""
from typing import Any, Mapping


def is_authorized_invoker(claims: Mapping[str, Any], audience: str, invoker_email: str) -> bool:
    if not audience or not invoker_email:
        return False
    if claims.get("aud") != audience or claims.get("email_verified") is not True:
        return False
    return str(claims.get("email") or "").strip().lower() == invoker_email.strip().lower()
