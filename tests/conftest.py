"""Keep the existing suite on the open-auth path. Login tests opt back in."""

import pytest

from core.config.settings import settings


@pytest.fixture(autouse=True)
def disable_auth_unless_a_test_opts_in(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REQUIRED", False)
