"""Tests for the persistence bootstrap and unit-of-work lifecycle."""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from db.uow import TariffConsumptionUnitofWork  # type: ignore[import-not-found]
from model.domain.tariff_model import Tariff  # type: ignore[import-not-found]


class PersistenceBootstrapTests(unittest.TestCase):
    def test_fake_backed_vivienda_route_needs_no_database_bootstrap(self) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"DB_HOST", "DB_PORT", "DB_USER", "DB_PSWD", "DB_NAME"}
        }
        env["SECRET_KEY"] = "x" * 64
        script = """
import os
import sys
class NoMysqlDrivers:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'MySQLdb', 'pymysql'}:
            raise ModuleNotFoundError(f'blocked {fullname}')
sys.meta_path.insert(0, NoMysqlDrivers())
sys.path.insert(0, 'tests')
from fakes import FakeUoW, make_client
from model.domain.household_model import Household
uow = FakeUoW()
uow.household_repository.add(Household(name='Casa'))
with make_client(uow) as client:
    response = client.get('/api/v1/households')
assert response.status_code == 200
assert [item['name'] for item in response.json()] == ['Casa']
assert not ({'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PSWD', 'DB_NAME'} & os.environ.keys())
"""
        result = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_importer_session_policy_keeps_driver_default_isolation(self) -> None:
        from db.database import create_session_factory

        with patch("db.database.create_engine") as create, patch(
            "db.database.sessionmaker"
        ) as maker:
            create_session_factory("mysql+pymysql://u:p@localhost/db?charset=utf8mb4")
        create.assert_called_once_with(
            "mysql+pymysql://u:p@localhost/db?charset=utf8mb4", pool_pre_ping=True
        )
        maker.assert_called_once_with(bind=create.return_value, expire_on_commit=False)

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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.orm import tariffs_table, tariff_versions_table, tariff_ranges_table
    engine = create_engine('sqlite://')
    for table in (tariffs_table, tariff_versions_table, tariff_ranges_table):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    env = {'DB_HOST': 'localhost', 'DB_PORT': '3306', 'DB_USER': 'u',
           'DB_PSWD': 'p', 'DB_NAME': 'db'}
    with patch.dict(os.environ, env, clear=True), \\
         patch('db.database.create_session_factory', return_value=factory) as build:
        assert main(['--sqlite', path, '--env-file', directory + '/missing']) == 0
        assert 'SECRET_KEY' not in os.environ
        build.assert_called_once_with(
            'mysql+pymysql://u:p@localhost:3306/db?charset=utf8mb4')
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_importer_persists_and_recovers_using_real_uow(self) -> None:
        script = """
import os
import sqlite3
import tempfile
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.orm import start_mappers, tariffs_table, tariff_versions_table, tariff_ranges_table
from db.uow import TariffConsumptionUnitofWork
from scripts.feed_tariffs_from_scrapper import main
with tempfile.TemporaryDirectory() as directory:
    path = directory + '/input.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE tariffs (id INTEGER, code TEXT)')
        db.execute('CREATE TABLE tiers (tariff_id INTEGER, year INTEGER, '
                   'month INTEGER, season TEXT, tier_order INTEGER, '
                   'max_kwh REAL, price_kwh TEXT)')
        db.execute("INSERT INTO tariffs VALUES (1, '1C')")
        db.executemany('INSERT INTO tiers VALUES (1, 2026, ?, ?, ?, ?, ?)', [
            (1, 'fuera de verano', 2, None, '2.0'),
            (1, 'fuera de verano', 1, 75, '1.0'),
            (2, 'fuera de verano', 1, 75, 'bad'),
            (3, 'fuera de verano', 1, 80, '1.5')])
    engine = create_engine('sqlite://')
    for table in (tariffs_table, tariff_versions_table, tariff_ranges_table):
        table.create(engine)
    start_mappers()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    env = {'DB_HOST': 'localhost', 'DB_PORT': '3306', 'DB_USER': 'u',
           'DB_PSWD': 'p', 'DB_NAME': 'db'}
    args = ['--sqlite', path, '--env-file', directory + '/missing']
    with patch.dict(os.environ, env, clear=True), \\
         patch('db.database.create_session_factory', return_value=factory), \\
         patch('db.orm.start_mappers'), \\
         patch('scripts.feed_tariffs_from_scrapper.logger.info') as info:
        assert main(args) == 1
        assert info.call_args.args[2:] == (2, 0, 0, 1)
        assert 'SECRET_KEY' not in os.environ
        with TariffConsumptionUnitofWork(factory) as uow:
            tariff = uow.tariff_repository.get_by_code('1C')
            january = uow.tariff_version_repository.get_by_tariff_and_period(
                tariff.id, 2026, 1)
            assert uow.tariff_version_repository.get_by_tariff_and_period(
                tariff.id, 2026, 2) is None
            ranges = uow.tariff_range_repository.list(tariff_version_id=january.id)
            assert [(r.range_min, r.range_max) for r in ranges] == [(0, 75), (75, None)]
        assert main(args + ['--dry-run']) == 0
        assert info.call_args.args[2:] == (1, 0, 2, 0)
        with sqlite3.connect(path) as db:
            db.execute("UPDATE tiers SET price_kwh='3.0' WHERE month=1 AND tier_order=1")
            db.execute("DELETE FROM tiers WHERE month=2")
        assert main(args) == 0
        assert info.call_args.args[2:] == (0, 0, 2, 0)
        assert main(args + ['--overwrite', '--months', '1']) == 0
        assert info.call_args.args[2:] == (0, 1, 0, 0)
        with TariffConsumptionUnitofWork(factory) as uow:
            ranges = uow.tariff_range_repository.list(tariff_version_id=january.id)
            assert len(ranges) == 2 and ranges[0].price_per_kwh == 3
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
