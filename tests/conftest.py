import pytest


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings between tests."""
    yield
