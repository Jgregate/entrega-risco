"""Faz o requests e o yfinance confiarem no mesmo CA store do Windows.

Em maquinas com antivirus que inspeciona HTTPS (AVG, Kaspersky, ESET...), o
Windows confia no certificado raiz que o antivirus instala, mas o Python nao:
`requests` e o `curl_cffi` (usado por dentro do yfinance) verificam contra o
bundle da lib `certifi`, que nao conhece esse certificado. O resultado e
`SSLCertVerificationError: unable to get local issuer certificate` em toda
chamada de rede.

Isso monta um bundle combinado (certifi + raizes do Windows) e aponta
`REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` pra ele, que e como tanto `requests`
quanto `curl_cffi` decidem qual CA usar.

O certificado que alguns desses antivirus geram (ex.: "AVG Web/Mail Shield
Root") nao marca a extensao Basic Constraints como critica — um detalhe fora
do RFC 5280 que o Python 3.13+ passou a rejeitar por padrao (`VERIFY_X509_STRICT`
ligado por default no `ssl.create_default_context`), mesmo com o certificado
corretamente confiavel. Por isso `sessao_requests()` monta um contexto SSL
com essa checagem extra desligada, so pra quem usa essa sessao — o restante
da verificacao de cadeia/validade continua normal.
"""

from __future__ import annotations

import os
import ssl
import tempfile
from pathlib import Path

import certifi
import requests
from requests.adapters import HTTPAdapter

_BUNDLE_PATH = Path(tempfile.gettempdir()) / "entrega-risco-cacert.pem"


def ensure_ca_bundle() -> None:
    if os.name != "nt":
        return
    if not _BUNDLE_PATH.exists():
        _BUNDLE_PATH.write_text(_build_bundle(), encoding="utf-8")
    os.environ.setdefault("CURL_CA_BUNDLE", str(_BUNDLE_PATH))


def _build_bundle() -> str:
    partes = [Path(certifi.where()).read_text(encoding="utf-8")]
    for loja in ("ROOT", "CA"):
        for certificado_der, _codificacao, _confiavel in ssl.enum_certificates(loja):
            partes.append(ssl.DER_cert_to_PEM_cert(certificado_der))
    return "\n".join(partes)


class _ContextoRelaxadoAdapter(HTTPAdapter):
    """HTTPAdapter que usa um SSLContext com VERIFY_X509_STRICT desligado."""

    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)


def sessao_requests() -> requests.Session:
    """Sessao requests apontada pro CA store do Windows nos sistemas onde
    isso e necessario; nos demais, e uma Session comum."""
    sessao = requests.Session()
    if os.name != "nt":
        return sessao

    ensure_ca_bundle()
    contexto = ssl.create_default_context(cafile=str(_BUNDLE_PATH))
    contexto.verify_flags &= ~ssl.VERIFY_X509_STRICT
    sessao.mount("https://", _ContextoRelaxadoAdapter(contexto))
    return sessao
