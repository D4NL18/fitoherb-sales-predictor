"""Parecer LGPD A-2: Vertex so em regiao permitida."""
import pytest


@pytest.mark.parametrize("raw,expected", [
    (None, "us-central1"), ("", "us-central1"), ("  ", "us-central1"),
    ("europe-west4", "europe-west4"), ("us-east5", "us-east5"), ("southamerica-east1", "southamerica-east1"),
])
def test_vertex_location_defaults_to_permitted_region(raw, expected):
    from tests.trend_insights.helpers import make_settings

    env = {} if raw is None else {"TREND_AI_LOCATION": raw}
    assert make_settings(**env).vertex_location == expected


@pytest.mark.parametrize("raw", ["global", "asia-southeast1", "GLOBAL"])
def test_vertex_location_outside_permitted_regions_is_refused(raw):
    from tests.trend_insights.helpers import make_settings

    with pytest.raises(ValueError):
        make_settings(TREND_AI_LOCATION=raw)
