import re
import unittest
from datetime import timedelta
from unittest import mock

from fakes import FakeUoW, make_client
from main import app
from model.domain.user_model import User
from routes import auth

PASSWORD = "Secret1!x"


class _UserRepo:
    def __init__(self):
        self.users = {}

    def get_by_username(self, username):
        return self.users.get(username)

    def add(self, user):
        self.users[user.username] = user


def _uow_with_user(is_active=True):
    uow = FakeUoW()
    uow.user_repository = _UserRepo()
    uow.user_repository.add(
        User(username="ana", email="a@x.com", full_name="Ana",
             hashed_password=auth.hash_password(PASSWORD), role="user",
             is_active=is_active)
    )
    return uow


class LoginTest(unittest.TestCase):
    def setUp(self):
        auth.auth_rate_limiter.requests.clear()

    def login(self, client, password):
        return client.post("/api/v1/auth/login",
                           data={"username": "ana", "password": password})

    def test_login_exitoso_devuelve_tokens(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.login(client, PASSWORD)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["token_type"], "bearer")
        self.assertTrue(r.json()["access_token"] and r.json()["refresh_token"])

    def test_token_de_login_autentica_en_me(self):
        with make_client(_uow_with_user(), user=None) as client:
            token = self.login(client, PASSWORD).json()["access_token"]
            r = client.get("/api/v1/auth/me",
                           headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["username"], "ana")

    def test_login_con_password_incorrecto_es_401(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.login(client, "wrong")
        self.assertEqual(r.status_code, 401)

    def test_login_de_usuario_inexistente_es_401(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = client.post("/api/v1/auth/login",
                            data={"username": "nadie", "password": PASSWORD})
        self.assertEqual(r.status_code, 401)

    def test_login_tras_cinco_intentos_es_429(self):
        with make_client(_uow_with_user(), user=None) as client:
            codes = [self.login(client, "wrong").status_code for _ in range(6)]
        self.assertEqual(codes, [401] * 5 + [429])


class RegisterTest(unittest.TestCase):
    body = {"username": "luis", "password": PASSWORD, "email": "l@x.com"}

    def post(self, client, body=None, key="k"):
        headers = {"x-api-key": key} if key else {}
        return client.post("/api/v1/auth/register", json=body or self.body,
                           headers=headers)

    def setUp(self):
        p = mock.patch.object(auth.require_register_key, "api_key", "k")
        p.start()
        self.addCleanup(p.stop)

    def test_registro_exitoso_crea_usuario_sin_exponer_password(self):
        uow = _uow_with_user()
        with make_client(uow, user=None) as client:
            r = self.post(client)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["username"], "luis")
        self.assertNotIn("password", r.text)
        self.assertIn("luis", uow.user_repository.users)
        self.assertTrue(uow.committed)

    def test_registro_con_username_existente_es_400(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.post(client, {**self.body, "username": "ana"})
        self.assertEqual(r.status_code, 400)

    def test_registro_con_password_debil_es_rechazado(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.post(client, {**self.body, "password": "weak"})
        self.assertEqual(r.status_code, 422)

    def test_registro_sin_api_key_es_403(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.post(client, key=None)
        self.assertEqual(r.status_code, 403)

    def test_registro_con_api_key_incorrecta_es_403(self):
        with make_client(_uow_with_user(), user=None) as client:
            r = self.post(client, key="bad")
        self.assertEqual(r.status_code, 403)


def _protected_routes():
    # app.routes no longer flattens included routers (FastAPI >= 0.14x); the
    # OpenAPI schema does, and it is the public surface anyway.
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v1/") and not path.startswith("/api/v1/auth/"):
            for method in operations.keys() & {"get", "post", "put", "delete", "patch"}:
                yield method.upper(), re.sub(r"\{[^}]+\}", "1", path)
    yield "GET", "/api/v1/auth/me"


class RutasProtegidasTest(unittest.TestCase):
    def check(self, headers):
        routes = list(_protected_routes())
        self.assertGreater(len(routes), 30)
        with make_client(_uow_with_user(), user=None) as client:
            for method, path in routes:
                with self.subTest(method=method, path=path):
                    r = client.request(method, path, headers=headers)
                    self.assertEqual(r.status_code, 401)

    def test_sin_token_responde_401(self):
        self.check({})

    def test_con_token_invalido_responde_401(self):
        self.check({"Authorization": "Bearer garbage"})

    def test_token_de_refresh_no_sirve_como_acceso(self):
        token = auth.create_refresh_token("ana")
        self.check({"Authorization": f"Bearer {token}"})

    def test_token_expirado_responde_401(self):
        token = auth.create_access_token("ana", timedelta(seconds=-10))
        self.check({"Authorization": f"Bearer {token}"})


if __name__ == "__main__":
    unittest.main()
