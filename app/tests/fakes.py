"""Shared fakes for route/handler tests (no MySQL needed).

Usage:
    uow = FakeUoW()
    uow.household_repository.add(Household(name="Casa"))
    with make_client(uow) as client:
        client.get("/api/v1/households")

- FakeRepository: in-memory store; add() assigns incremental ids.
  Subclass or monkeypatch for entity-specific queries (e.g. list filters).
- FakeUoW: one FakeRepository per attribute of TariffConsumptionUnitofWork.
  Tracks `committed`. Re-entering returns the same instance, so state
  persists between requests and the test can inspect it afterwards.
- make_client(uow): TestClient over the real app where every module's
  `TariffConsumptionUnitofWork` is replaced by `uow` and `get_current_user`
  is overridden (pass `user=None` to keep real auth and test 401s).
"""
import os
from contextlib import ExitStack
from itertools import count
from sys import modules
from unittest import mock

from fastapi.testclient import TestClient

# config.py needs these at import time; engine creation is lazy (no connection).
os.environ.setdefault("SECRET_KEY", "x" * 64)
os.environ.setdefault("DB_PORT", "3306")
for _k in ("DB_HOST", "DB_USER", "DB_PSWD", "DB_NAME"):
    os.environ.setdefault(_k, "unused")

from common.services.auth_dependency import get_current_user
from main import app
from model.auth import UserPublic

_REPOSITORIES = (
    "url_shotner_repository",
    "household_repository",
    "household_tariff_repository",
    "tariff_repository",
    "meter_reading_repository",
    "billing_period_repository",
    "tariff_range_repository",
    "tariff_version_repository",
    "user_repository",
)

DEFAULT_USER = UserPublic(
    username="tester", email="t@example.com", full_name="Tester", role="user"
)


class FakeRepository:
    def __init__(self):
        self.items = {}
        self._ids = count(1)

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = next(self._ids)
        self.items[item.id] = item

    def get(self, id):
        return self.items.get(id)

    def list(self, limit=100, offset=0, **_):
        return list(self.items.values())[offset : offset + limit]

    def delete(self, item):
        self.items.pop(item.id, None)


class FakeUoW:
    def __init__(self):
        for name in _REPOSITORIES:
            setattr(self, name, FakeRepository())
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __call__(self):
        return self

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def make_client(uow, user=DEFAULT_USER):
    """Return a TestClient (use as context manager) wired to `uow`."""
    stack = ExitStack()
    for module in list(modules.values()):
        if getattr(module, "TariffConsumptionUnitofWork", None) is not None:
            stack.enter_context(
                mock.patch.object(module, "TariffConsumptionUnitofWork", uow)
            )
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    stack.callback(app.dependency_overrides.clear)

    client = TestClient(app)
    original_exit = client.__exit__
    client.__exit__ = lambda *a: (original_exit(*a), stack.close())[0]
    return client
