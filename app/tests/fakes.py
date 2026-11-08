"""Shared fakes for route/handler tests (no MySQL needed).

Usage:
    uow = FakeUoW()
    uow.household_repository.add(Household(name="Casa"))
    with make_client(uow) as client:
        client.get("/api/v1/households")

- FakeRepository: in-memory store; add() assigns incremental ids.
  list() filters by any keyword naming an item attribute; entity-specific
  queries live in the Fake*Repository subclasses below.
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

    def list(self, limit=100, offset=0, **filters):
        """Filter by every non-None keyword that names an item attribute."""
        rows = [
            i for i in self.items.values()
            if all(getattr(i, k, None) == v for k, v in filters.items() if v is not None)
        ]
        return rows[offset : offset + limit]

    def get_by_code(self, code):
        return next((i for i in self.items.values() if i.code == code), None)

    def delete(self, item):
        self.items.pop(item.id, None)


class FakeMeterReadingRepository(FakeRepository):
    """Adds the date-range queries of the real MeterReadingRepository."""

    def get_by_household_and_date(self, household_id, reading_date):
        return next(
            (r for r in self.items.values()
             if r.household_id == household_id and r.reading_date == reading_date),
            None,
        )

    def list(self, household_id=None, reading_date_from=None, reading_date_to=None,
             limit=100, offset=0, **filters):
        rows = [
            r for r in super().list(limit=len(self.items), household_id=household_id, **filters)
            if (reading_date_from is None or r.reading_date >= reading_date_from)
            and (reading_date_to is None or r.reading_date <= reading_date_to)
        ]
        return sorted(rows, key=lambda r: r.reading_date)[offset : offset + limit]

    def _range(self, household_id, reading_date_from, reading_date_to):
        return self.list(household_id=household_id, reading_date_from=reading_date_from,
                         reading_date_to=reading_date_to, limit=10**6)

    def get_first_reading_in_range(self, household_id, reading_date_from, reading_date_to):
        rows = self._range(household_id, reading_date_from, reading_date_to)
        return rows[0] if rows else None

    def get_last_reading_in_range(self, household_id, reading_date_from, reading_date_to):
        rows = self._range(household_id, reading_date_from, reading_date_to)
        return rows[-1] if rows else None


class FakeTariffVersionRepository(FakeRepository):
    def get_by_tariff_and_period(self, tariff_id, year, month):
        return next(
            (v for v in self.items.values()
             if (v.tariff_id, v.year, v.month) == (tariff_id, year, month)),
            None,
        )

    def get_by_tariff_and_period_or_latest_before(self, tariff_id, year, month):
        """Mimics the real repo: exact month, else latest earlier version."""
        earlier = [
            v for v in self.items.values()
            if v.tariff_id == tariff_id and (v.year, v.month) <= (year, month)
        ]
        return max(earlier, key=lambda v: (v.year, v.month), default=None)


class FakeUoW:
    def __init__(self):
        for name in _REPOSITORIES:
            setattr(self, name, FakeRepository())
        self.meter_reading_repository = FakeMeterReadingRepository()
        self.tariff_version_repository = FakeTariffVersionRepository()
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

    class _Client(TestClient):
        def __exit__(self, *args):
            try:
                return super().__exit__(*args)
            finally:
                stack.close()

    return _Client(app)
