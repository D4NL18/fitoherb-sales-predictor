import pytest

from tests.trend_insights.helpers import FakeClock, FakeObjectStore, make_rig


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def objects():
    return FakeObjectStore()


@pytest.fixture
def rig():
    return make_rig()
