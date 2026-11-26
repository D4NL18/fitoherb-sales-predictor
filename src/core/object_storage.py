"""
Wrapper fino de `google-cloud-storage` para objetos JSON com concorrencia otimista (ADR-009 DA-06/DA-07).
Compartilhado entre `analytics` (indice de afinidade) e a F7. O SDK so e importado na primeira chamada e o
cliente usa as credenciais padrao (ADC) do Cloud Run. Erros do SDK viram `ObjectStorageUnavailable` /
`ObjectPreconditionFailed`: o texto da excecao do SDK nunca vai ao log nem a resposta (so o tipo).
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("fitoherb.object_storage")

GCS_URI_PREFIX = "gs://"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
NEW_OBJECT_GENERATION = 0  # `if_generation_match=0`: so cria se o objeto nao existir


class ObjectStorageUnavailable(Exception):
    """Armazenamento inacessivel (rede, permissao, bucket ausente, objeto ilegivel)."""


class ObjectPreconditionFailed(Exception):
    """Precondicao de geracao falhou (HTTP 412): outro escritor chegou antes."""


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    """`gs://bucket/caminho/objeto.json` -> `("bucket", "caminho/objeto.json")`."""
    if not uri.startswith(GCS_URI_PREFIX):
        raise ValueError("URI GCS deve comecar com gs://")
    bucket, _, path = uri[len(GCS_URI_PREFIX):].partition("/")
    if not bucket or not path:
        raise ValueError("URI GCS deve ter bucket e caminho do objeto")
    return bucket, path


class GcsJsonStorage:
    """Leitura/escrita de JSON em um bucket; `client` injetavel para testes (sem rede)."""

    def __init__(self, bucket_name: str, client: Any = None, api_errors: Any = None):
        self._bucket_name = bucket_name
        self._client = client
        self._errors = api_errors  # namespace com NotFound/PreconditionFailed/GoogleAPIError (dublê nos testes)

    def _bucket(self):
        if self._client is None:
            from google.cloud import storage  # importacao tardia: nada acessa rede ao importar o modulo

            self._client = storage.Client()
        return self._client.bucket(self._bucket_name)

    def _api_errors(self):
        if self._errors is None:
            from google.api_core import exceptions as gcs_errors

            self._errors = gcs_errors
        return self._errors

    def read_json(self, path: str) -> Optional[Tuple[Any, int]]:
        """`(conteudo, geracao)` ou `None` se o objeto nao existe; conteudo ilegivel e erro de armazenamento."""
        errors = self._api_errors()
        try:
            blob = self._bucket().get_blob(path)
            if blob is None:
                return None
            return json.loads(blob.download_as_text()), int(blob.generation)
        except errors.NotFound:
            return None
        except (errors.GoogleAPIError, OSError, ValueError) as exc:
            logger.warning("object_storage.read_failed type=%s", type(exc).__name__)
            raise ObjectStorageUnavailable() from None

    def get_generation(self, path: str) -> Optional[int]:
        """Geracao atual do objeto so pelos metadados (sem baixar o corpo); `None` se nao existe."""
        errors = self._api_errors()
        try:
            blob = self._bucket().get_blob(path)
            return None if blob is None else int(blob.generation)
        except errors.NotFound:
            return None
        except (errors.GoogleAPIError, OSError) as exc:
            logger.warning("object_storage.metadata_failed type=%s", type(exc).__name__)
            raise ObjectStorageUnavailable() from None

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        errors = self._api_errors()
        try:
            blob = self._bucket().blob(path)
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=False, default=str), content_type=JSON_CONTENT_TYPE,
                if_generation_match=if_generation_match,
            )
            return int(blob.generation)
        except errors.PreconditionFailed:
            raise ObjectPreconditionFailed() from None
        except (errors.GoogleAPIError, OSError) as exc:
            logger.warning("object_storage.write_failed type=%s", type(exc).__name__)
            raise ObjectStorageUnavailable() from None

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        errors = self._api_errors()
        try:
            self._bucket().blob(path).delete(if_generation_match=if_generation_match)
        except (errors.NotFound, errors.PreconditionFailed):
            return
        except (errors.GoogleAPIError, OSError) as exc:
            logger.warning("object_storage.delete_failed type=%s", type(exc).__name__)
            raise ObjectStorageUnavailable() from None


def _create_lease(storage: GcsJsonStorage, path: str, expires_at: datetime) -> bool:
    try:
        storage.write_json(path, {"expiresAt": expires_at.isoformat()}, if_generation_match=NEW_OBJECT_GENERATION)
        return True
    except ObjectPreconditionFailed:
        return False


def try_acquire_lease(storage: GcsJsonStorage, path: str, ttl_seconds: int, clock: Callable[[], datetime]) -> bool:
    """Cria o lease com geracao 0; lease vencido e removido com a geracao lida e recriado; valido e recusado."""
    now = clock()
    if _create_lease(storage, path, now + timedelta(seconds=ttl_seconds)):
        return True
    existing = storage.read_json(path)
    if existing is not None and datetime.fromisoformat(existing[0]["expiresAt"]) > now:
        return False
    storage.delete(path, if_generation_match=existing[1] if existing else None)
    return _create_lease(storage, path, now + timedelta(seconds=ttl_seconds))


def release_lease(storage: GcsJsonStorage, path: str) -> None:
    storage.delete(path)
