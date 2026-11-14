"""Tests for the persistence bootstrap and unit-of-work lifecycle."""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from db.uow import TariffConsumptionUnitofWork  # type: ignore[import-not-found]
from model.domain.tariff_model import Tariff  # type: ignore[import-not-found]


class PersistenceBootstrapTests(unittest.TestCase):
    def test_real_uow_commits_and_rolls_back_tariffs(self) -> None:
        script = """
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.orm import start_mappers, tariffs_table
from db.uow import TariffConsumptionUnitofWork
from model.domain.tariff_model import Tariff
start_mappers()
engine = create_engine('sqlite://')
tariffs_table.create(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False)
with TariffConsumptionUnitofWork(factory) as uow:
    uow.tariff_repository.add(Tariff(code='1C', description='committed'))
    uow.commit()
with TariffConsumptionUnitofWork(factory) as uow:
    assert uow.tariff_repository.get_by_code('1C') is not None
    uow.tariff_repository.add(Tariff(code='1D', description='rolled back'))
    uow.rollback()
with TariffConsumptionUnitofWork(factory) as uow:
    assert uow.tariff_repository.get_by_code('1D') is None
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_importer_uses_configured_session_context(self) -> None:
        script = """
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch
from scripts.feed_tariffs_from_scrapper import main
with tempfile.TemporaryDirectory() as directory:
    path = directory + '/scraped.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE tariffs (id INTEGER, code TEXT)')
        db.execute('CREATE TABLE tiers (tariff_id INTEGER, year INTEGER, '
                   'month INTEGER, season TEXT, tier_order INTEGER, '
                   'max_kwh REAL, price_kwh REAL)')
    session = MagicMock()
    factory = MagicMock(return_value=session)
    env = {'DB_HOST': 'localhost', 'DB_PORT': '3306', 'DB_USER': 'u',
           'DB_PSWD': 'p', 'DB_NAME': 'db'}
    with patch.dict(os.environ, env, clear=True), \\
         patch('sqlalchemy.create_engine'), \\
         patch('sqlalchemy.orm.sessionmaker', return_value=factory):
        assert main(['--sqlite', path, '--env-file', directory + '/missing']) == 0
    assert session.close.called
    assert not session.commit.called
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_authenticated_startup_validates_secret(self) -> None:
        for secret, expected in [(None, False), ("short", False), ("x" * 64, True)]:
            with self.subTest(secret=secret):
                env = os.environ.copy()
                env.pop("SECRET_KEY", None)
                if secret is not None:
                    env["SECRET_KEY"] = secret
                result = subprocess.run(
                    [sys.executable, "-c", "import main; assert main.app"],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode == 0, expected, result.stderr)
                if not expected:
                    self.assertIn("SECRET_KEY", result.stderr)

    def test_supplied_factory_uses_one_session_and_explicit_transactions(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        tariff = Tariff(code="1C", description="test")
        with patch("db.uow.default_session_factory", side_effect=AssertionError):
            with TariffConsumptionUnitofWork(factory) as uow:
                uow.tariff_repository.add(tariff)
                self.assertIs(uow.household_repository.session, session)
                self.assertIs(uow.url_shotner_repository.session, session)
                uow.commit()
                uow.rollback()
        session.add.assert_called_once_with(tariff)
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()
        session.close.assert_called()

    def test_exception_propagates_and_session_is_released_without_commit(self) -> None:
        session = MagicMock()
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with TariffConsumptionUnitofWork(lambda **kwargs: session):
                raise RuntimeError("failure")
        session.close.assert_called()
        session.commit.assert_not_called()
        session.rollback.assert_not_called()

    def test_default_contexts_reuse_factory_but_not_sessions(self) -> None:
        script = """
from unittest.mock import MagicMock, patch
from db.uow import TariffConsumptionUnitofWork
sessions = [MagicMock(), MagicMock()]
engine = MagicMock()
factory = MagicMock(side_effect=sessions)
with patch('db.database.create_engine', return_value=engine) as create, \\
     patch('db.database.sessionmaker', return_value=factory) as maker:
    with TariffConsumptionUnitofWork() as first:
        assert first.session is sessions[0]
    with TariffConsumptionUnitofWork() as second:
        assert second.session is sessions[1]
    assert create.call_count == maker.call_count == 1
    assert create.call_args.kwargs == {
        'isolation_level': 'REPEATABLE READ', 'pool_pre_ping': True}
    assert maker.call_args.kwargs == {'bind': engine, 'expire_on_commit': False}
    assert all(s.close.called for s in sessions)
    assert all(not s.commit.called for s in sessions)
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_import_without_authentication_or_engine(self) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {"SECRET_KEY", "DB_HOST", "DB_PORT", "DB_USER", "DB_PSWD", "DB_NAME"}
        }
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
import sqlalchemy
def forbidden(*args, **kwargs):
    raise AssertionError("engine constructed during import")
sqlalchemy.create_engine = forbidden
import db.uow
assert 'common.config' not in sys.modules
assert 'common.logging' not in sys.modules
assert 'MySQLdb' not in sys.modules
""",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
