"""
Adaptador GCS da porta `ObjectStore` (unico ponto com o SDK `google-cloud-storage`). Escrita com
`if_generation_match` (0 = so cria); falhas de rede/permissao viram `ObjectStoreUnavailable` sem a mensagem do SDK.
O cliente e criado na primeira chamada (ADC da conta de servico do Cloud Run); nada e acessado ao importar.
"""
import json
import logging
from typing import Any, Optional, Tuple

from src.modules.trend_insights.domain.constants import LOGGER_NAME
from src.modules.trend_insights.domain.ports import ObjectConflict, ObjectStoreUnavailable

logger = logging.getLogger(LOGGER_NAME + ".gcs")
JSON_CONTENT_TYPE = "application/json; charset=utf-8"


class GcsObjectStore:
    def __init__(self, bucket_name: str, client: Any = None):
        self._bucket_name = bucket_name
        self._client = client

    def _bucket(self):
        if self._client is None:
            from google.cloud import storage  # importacao tardia: so existe com a dependencia instalada

            self._client = storage.Client()
        return self._client.bucket(self._bucket_name)

    def read_json(self, path: str) -> Optional[Tuple[Any, int]]:
        from google.api_core import exceptions as gcs_errors

        try:
            blob = self._bucket().get_blob(path)
            if blob is None:
                return None
            return json.loads(blob.download_as_text()), int(blob.generation)
        except gcs_errors.NotFound:
            return None
        except (gcs_errors.GoogleAPIError, OSError, ValueError) as exc:
            logger.warning("tia.gcs.read_failed type=%s", type(exc).__name__)
            raise ObjectStoreUnavailable() from None

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        from google.api_core import exceptions as gcs_errors

        try:
            blob = self._bucket().blob(path)
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=False, default=str), content_type=JSON_CONTENT_TYPE,
                if_generation_match=if_generation_match,
            )
            return int(blob.generation)
        except gcs_errors.PreconditionFailed:
            raise ObjectConflict() from None
        except (gcs_errors.GoogleAPIError, OSError) as exc:
            logger.warning("tia.gcs.write_failed type=%s", type(exc).__name__)
            raise ObjectStoreUnavailable() from None

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        from google.api_core import exceptions as gcs_errors

        try:
            self._bucket().blob(path).delete(if_generation_match=if_generation_match)
        except (gcs_errors.NotFound, gcs_errors.PreconditionFailed):
            return
        except (gcs_errors.GoogleAPIError, OSError) as exc:
            logger.warning("tia.gcs.delete_failed type=%s", type(exc).__name__)
            raise ObjectStoreUnavailable() from None


class UnavailableObjectStore:
    """Usado sem bucket configurado: toda leitura/escrita falha, e a F7 cai fechada (templates)."""

    def read_json(self, path: str):
        raise ObjectStoreUnavailable()

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        raise ObjectStoreUnavailable()

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        raise ObjectStoreUnavailable()
