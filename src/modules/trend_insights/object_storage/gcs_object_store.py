"""
Adaptador GCS da porta `ObjectStore` (unico ponto com o SDK `google-cloud-storage`). Escrita com
`if_generation_match` (0 = so cria); falhas de rede/permissao viram `ObjectStoreUnavailable` sem a mensagem do SDK.
O cliente e criado na primeira chamada (ADC da conta de servico do Cloud Run); nada e acessado ao importar.
"""
from pathlib import Path
import hashlib
import json
import logging
import threading
from typing import Any, List, Optional, Tuple

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

    def paths(self, prefix: str) -> List[str]:
        """Caminhos dos objetos sob o prefixo (so nomes; usado na contagem de radares do `health`)."""
        from google.api_core import exceptions as gcs_errors

        try:
            return [blob.name for blob in self._bucket().list_blobs(prefix=prefix)]
        except (gcs_errors.GoogleAPIError, OSError) as exc:
            logger.warning("tia.gcs.list_failed type=%s", type(exc).__name__)
            raise ObjectStoreUnavailable() from None


class UnavailableObjectStore:
    """Usado sem bucket configurado: toda leitura/escrita falha, e a F7 cai fechada (templates)."""

    def read_json(self, path: str):
        raise ObjectStoreUnavailable()

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        raise ObjectStoreUnavailable()

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        raise ObjectStoreUnavailable()

    def paths(self, prefix: str) -> List[str]:
        raise ObjectStoreUnavailable()


class LocalFileObjectStore:
    """Armazenamento local em JSON com controle de geracao para desenvolvimento sem bucket GCS."""

    def __init__(self, root: Path):
        self._root = root
        self._lock = threading.Lock()
        self._generations: dict[str, int] = {}

    def _target(self, path: str) -> Path:
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:32]
        return self._root / f"{digest}.json"

    def read_json(self, path: str) -> Optional[Tuple[Any, int]]:
        with self._lock:
            file_path = self._target(path)
            if not file_path.exists():
                return None
            gen = self._generations.get(path, 1)
            envelope = json.loads(file_path.read_text(encoding="utf-8"))
            return envelope["payload"], gen

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        with self._lock:
            file_path = self._target(path)
            current = self._generations.get(path, 1) if file_path.exists() else 0
            if current != if_generation_match:
                raise ObjectConflict()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            envelope = {"path": path, "payload": payload}
            file_path.write_text(json.dumps(envelope, ensure_ascii=False, default=str), encoding="utf-8")
            new_gen = current + 1
            self._generations[path] = new_gen
            return new_gen

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        with self._lock:
            file_path = self._target(path)
            if not file_path.exists():
                return
            current = self._generations.get(path, 1)
            if if_generation_match is not None and current != if_generation_match:
                return
            file_path.unlink(missing_ok=True)
            self._generations.pop(path, None)

    def paths(self, prefix: str) -> List[str]:
        with self._lock:
            if not self._root.exists():
                return []
            prefix_norm = prefix.strip("/")
            results: List[str] = []
            for p in self._root.glob("*.json"):
                try:
                    stored_path = json.loads(p.read_text(encoding="utf-8")).get("path", "")
                except (OSError, ValueError):
                    continue
                if stored_path.startswith(prefix_norm):
                    results.append(stored_path)
            return results
