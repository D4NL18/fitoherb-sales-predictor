"""F-02 (seguranca): o verificador OIDC reaproveita os certificados do Google (TTL curto) e filtra token lixo sem rede."""
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import mod

TOKEN = "aaa.bbb.ccc"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _rig(status=200, ttl=300):
    network = []

    def inner(url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        network.append(url)
        return SimpleNamespace(status=status, data=b"{}", headers={})

    def verify_fn(token, request, audience):
        request("https://certs.example/keys", method="GET")
        return {"aud": audience, "email": "x@y.com"}

    clock = Clock()
    verifier = mod("auth.oidc_verifier").GoogleOidcVerifier(
        request=inner, verify_fn=verify_fn, clock=clock, certs_ttl_seconds=ttl)
    return verifier, network, clock


def test_certificates_are_fetched_once_within_ttl():
    verifier, network, _ = _rig()
    verifier.verify(TOKEN, "aud")
    verifier.verify(TOKEN, "aud")
    assert len(network) == 1


def test_certificates_are_refetched_after_ttl():
    verifier, network, clock = _rig(ttl=300)
    verifier.verify(TOKEN, "aud")
    clock.now += 301
    verifier.verify(TOKEN, "aud")
    assert len(network) == 2


def test_failed_certificate_response_is_not_cached():
    verifier, network, _ = _rig(status=500)
    verifier.verify(TOKEN, "aud")
    verifier.verify(TOKEN, "aud")
    assert len(network) == 2


@pytest.mark.parametrize("token", ["", "lixo", "a.b", "a.b.c.d", "a." + "b" * 5000 + ".c", None])
def test_garbage_token_is_rejected_without_network(token):
    verifier, network, _ = _rig()
    with pytest.raises(ValueError):
        verifier.verify(token, "aud")
    assert network == []

