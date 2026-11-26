"""T-7.0c.1 / T-7.0c.2: armazenamento do indice de afinidade (local x GCS), lease e refresh por geracao.
Nenhum teste toca rede: o cliente GCS e um dublê em memoria."""
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import FakeClock

storage_mod = pytest.importorskip("src.core.object_storage")
aff_svc = pytest.importorskip("src.modules.analytics.service.product_affinity_service")

class _GoogleAPIError(Exception):
    pass


class _NotFound(_GoogleAPIError):
    pass


class _PreconditionFailed(_GoogleAPIError):
    pass


gcs_errors = SimpleNamespace(NotFound=_NotFound, PreconditionFailed=_PreconditionFailed, GoogleAPIError=_GoogleAPIError)
BUCKET, PATH = "bkt", "affinity/index.json"
LOCK = "locks/affinity-sync.lock"


class FakeBlob:
    def __init__(self, bucket, name):
        self._bucket, self.name = bucket, name

    @property
    def generation(self):
        return self._bucket.objects[self.name][1]

    def download_as_text(self):
        return self._bucket.objects[self.name][0]

    def upload_from_string(self, text, content_type=None, if_generation_match=None):
        current = self._bucket.objects.get(self.name)
        if if_generation_match is not None and (current[1] if current else 0) != if_generation_match:
            raise gcs_errors.PreconditionFailed("412")
        self._bucket.counter += 1
        self._bucket.objects[self.name] = (text, self._bucket.counter)

    def delete(self, if_generation_match=None):
        current = self._bucket.objects.get(self.name)
        if current is None:
            raise gcs_errors.NotFound("404")
        if if_generation_match is not None and current[1] != if_generation_match:
            raise gcs_errors.PreconditionFailed("412")
        del self._bucket.objects[self.name]


class FakeBucket:
    def __init__(self):
        self.objects, self.counter, self.metadata_reads = {}, 100, 0

    def get_blob(self, name):
        self.metadata_reads += 1
        return FakeBlob(self, name) if name in self.objects else None

    def blob(self, name):
        return FakeBlob(self, name)


class FakeClient:
    def __init__(self):
        self.bucket_obj = FakeBucket()

    def bucket(self, name):
        assert name == BUCKET
        return self.bucket_obj


def _storage():
    client = FakeClient()
    return storage_mod.GcsJsonStorage(BUCKET, client=client, api_errors=gcs_errors), client.bucket_obj


# ----------------------------------------------------------------------------- src/core/object_storage
def test_parse_gcs_uri():
    assert storage_mod.parse_gcs_uri("gs://bkt/affinity/index.json") == ("bkt", "affinity/index.json")
    for bad in ("http://x/y", "gs://bkt", "gs:///obj"):
        with pytest.raises(ValueError):
            storage_mod.parse_gcs_uri(bad)


def test_read_json_missing_is_none_and_write_round_trips_generation():
    storage, _ = _storage()
    assert storage.read_json(PATH) is None and storage.get_generation(PATH) is None
    generation = storage.write_json(PATH, {"a": 1}, if_generation_match=0)
    assert storage.read_json(PATH) == ({"a": 1}, generation) and storage.get_generation(PATH) == generation


def test_write_with_stale_generation_raises_precondition_failed_and_keeps_object():
    storage, _ = _storage()
    first = storage.write_json(PATH, {"v": 1}, if_generation_match=0)
    with pytest.raises(storage_mod.ObjectPreconditionFailed):
        storage.write_json(PATH, {"v": 2}, if_generation_match=first - 1)
    with pytest.raises(storage_mod.ObjectPreconditionFailed):
        storage.write_json(PATH, {"v": 3}, if_generation_match=0)
    assert storage.read_json(PATH)[0] == {"v": 1}


def test_unreadable_content_is_storage_unavailable_without_leaking_text():
    storage, bucket = _storage()
    bucket.objects[PATH] = ("{nao e json", 5)
    with pytest.raises(storage_mod.ObjectStorageUnavailable) as raised:
        storage.read_json(PATH)
    assert "nao e json" not in str(raised.value)


def test_lease_blocks_while_valid_and_recovers_expired():
    storage, bucket = _storage()
    clock = FakeClock()
    assert storage_mod.try_acquire_lease(storage, LOCK, 300, clock) is True
    assert storage_mod.try_acquire_lease(storage, LOCK, 300, clock) is False
    clock.advance(301)
    assert storage_mod.try_acquire_lease(storage, LOCK, 300, clock) is True
    storage_mod.release_lease(storage, LOCK)
    assert LOCK not in bucket.objects
    storage_mod.release_lease(storage, LOCK)  # idempotente


# ----------------------------------------------------------------------------- AffinityIndexStore
INDEX_V1 = {"meta": {"last_sync_at": "t1"}, "skus": {"1": {"description": "A"}}, "affinities": {"1": []}}
INDEX_V2 = {"meta": {"last_sync_at": "t2"}, "skus": {"1": {"description": "A"}}, "affinities": {"1": []}}


@pytest.fixture
def gcs_index(monkeypatch):
    storage, bucket = _storage()
    clock = FakeClock()
    store = aff_svc.GcsAffinityIndexStore(storage, PATH, clock)
    aff_svc.reset_product_affinity_memory_cache()
    aff_svc.configure_index_store(store, clock=clock)
    events = []
    aff_svc.register_index_changed_listener(lambda: events.append("changed"))
    yield storage, bucket, clock, events
    aff_svc.configure_index_store(None)
    aff_svc.clear_index_changed_listeners()
    aff_svc.reset_product_affinity_memory_cache()


def test_without_gcs_uri_the_local_store_is_used(monkeypatch, tmp_path):
    monkeypatch.delenv("AFFINITY_INDEX_GCS_URI", raising=False)
    aff_svc.configure_index_store(None)
    assert isinstance(aff_svc.get_index_store(tmp_path / "x.json"), aff_svc.LocalAffinityIndexStore)


def test_with_gcs_uri_the_gcs_store_is_used(monkeypatch):
    monkeypatch.setenv("AFFINITY_INDEX_GCS_URI", "gs://bkt/affinity/index.json")
    aff_svc.configure_index_store(None)
    store = aff_svc.get_index_store(aff_svc.DEFAULT_INDEX_PATH)
    assert isinstance(store, aff_svc.GcsAffinityIndexStore) and store.path == "affinity/index.json"
    aff_svc.configure_index_store(None)


def test_missing_object_returns_none_without_rebuilding(gcs_index):
    assert aff_svc.get_loaded_affinity_index() is None
    assert aff_svc.get_affinity_lookup_map() is None and aff_svc.get_product_affinities("1") is None


def test_first_call_loads_then_refresh_only_every_15_minutes_by_metadata(gcs_index):
    storage, bucket, clock, events = gcs_index
    storage.write_json(PATH, INDEX_V1, if_generation_match=0)
    assert aff_svc.get_loaded_affinity_index()["meta"]["last_sync_at"] == "t1"
    reads = bucket.metadata_reads
    clock.advance(14 * 60)
    aff_svc.get_loaded_affinity_index()
    assert bucket.metadata_reads == reads  # dentro dos 15 min nao consulta o GCS
    clock.advance(2 * 60)
    aff_svc.get_loaded_affinity_index()
    assert events == []  # geracao igual: nao recarrega nem avisa


def test_new_generation_reloads_and_notifies_listeners(gcs_index):
    storage, _, clock, events = gcs_index
    generation = storage.write_json(PATH, INDEX_V1, if_generation_match=0)
    aff_svc.get_loaded_affinity_index()
    storage.write_json(PATH, INDEX_V2, if_generation_match=generation)
    clock.advance(aff_svc.AFFINITY_INDEX_REFRESH_MINUTES * 60 + 1)
    assert aff_svc.get_loaded_affinity_index()["meta"]["last_sync_at"] == "t2"
    assert events == ["changed"]


def test_storage_failure_on_refresh_keeps_previous_index(gcs_index, monkeypatch):
    storage, _, clock, events = gcs_index
    storage.write_json(PATH, INDEX_V1, if_generation_match=0)
    aff_svc.get_loaded_affinity_index()
    monkeypatch.setattr(storage, "get_generation", lambda path: (_ for _ in ()).throw(storage_mod.ObjectStorageUnavailable()))
    clock.advance(16 * 60)
    assert aff_svc.get_loaded_affinity_index()["meta"]["last_sync_at"] == "t1" and events == []


def _catalog():
    return {"1": {"sku": "1", "description": "CREATINA A", "category": "C", "supplier": "ALFA", "active": True,
                  "current_price": 10.0, "last_cost": 5.0, "current_stock": 3}}


def test_sync_writes_to_gcs_and_releases_lease(gcs_index):
    storage, bucket, _, events = gcs_index
    summary = aff_svc.sync_product_affinity_index(catalog_loader=_catalog, gallery_loader=lambda: [])
    assert summary["recomputed"] is True
    stored = storage.read_json(PATH)[0]
    assert "1" in stored["skus"] and "locks/affinity-sync.lock" not in bucket.objects


def test_sync_conflict_does_not_overwrite_and_is_reported(gcs_index, monkeypatch):
    storage, _, _, _ = gcs_index
    generation = storage.write_json(PATH, INDEX_V1, if_generation_match=0)
    original = aff_svc.compute_affinity_matrix

    def rival_writes_during_compute(*args, **kwargs):
        storage.write_json(PATH, INDEX_V2, if_generation_match=generation)  # escritor sem lease chega antes
        return original(*args, **kwargs)

    monkeypatch.setattr(aff_svc, "compute_affinity_matrix", rival_writes_during_compute)
    with pytest.raises(aff_svc.AffinityIndexConflictError):
        aff_svc.sync_product_affinity_index(catalog_loader=_catalog, gallery_loader=lambda: [], force=True)
    assert storage.read_json(PATH)[0] == INDEX_V2  # o escritor que chegou antes permanece
    assert aff_svc.get_loaded_affinity_index()["meta"]["last_sync_at"] == "t2"  # memoria realinhada


def test_concurrent_sync_is_refused_while_lease_is_held(gcs_index):
    storage, _, clock, _ = gcs_index
    assert storage_mod.try_acquire_lease(storage, "locks/affinity-sync.lock", 300, clock)
    called = []
    with pytest.raises(aff_svc.AffinitySyncBusyError):
        aff_svc.sync_product_affinity_index(catalog_loader=lambda: called.append(1) or _catalog(), gallery_loader=lambda: [])
    assert called == []


def test_lease_is_released_even_when_sync_fails(gcs_index):
    _, bucket, _, _ = gcs_index

    def boom():
        raise RuntimeError("erro do ERP")

    with pytest.raises(RuntimeError):
        aff_svc.sync_product_affinity_index(catalog_loader=boom, gallery_loader=lambda: [])
    assert "locks/affinity-sync.lock" not in bucket.objects
