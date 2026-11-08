import os

# common.config exige SECRET_KEY (>= 64 chars) y db.database construye el engine
# (perezoso, sin conectar) al importarse: valores de relleno bastan.
os.environ.setdefault("SECRET_KEY", "k" * 64)
for _k, _v in (("DB_HOST", "localhost"), ("DB_PORT", "3306"), ("DB_USER", "u"),
               ("DB_PSWD", "p"), ("DB_NAME", "d")):
    os.environ.setdefault(_k, _v)

from datetime import datetime, timedelta, timezone  # noqa: E402
import unittest  # noqa: E402
from unittest import mock

from jose import jwt

from middleware.rate_limit import RateLimiter
from routes import auth
from common.config import SECRET_KEY
from common.services.auth_dependency import ALGORITHM


class HashDeContrasenaTest(unittest.TestCase):
    def test_verifica_contrasena_correcta_e_incorrecta(self):
        hashed = auth.hash_password("secreto123")
        self.assertNotEqual(hashed, "secreto123")
        self.assertTrue(auth.verify_password("secreto123", hashed))
        self.assertFalse(auth.verify_password("otra", hashed))


class JwtTest(unittest.TestCase):
    def _decode(self, token):
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_token_valido(self):
        claims = self._decode(auth.create_access_token("ana"))
        self.assertEqual(claims["sub"], "ana")
        self.assertEqual(claims["token_type"], "access")

    def test_refresh_token_tipo_refresh(self):
        self.assertEqual(self._decode(auth.create_refresh_token("ana"))["token_type"], "refresh")

    def test_token_vencido(self):
        token = auth.create_access_token("ana", expires_delta=timedelta(seconds=-10))
        with self.assertRaises(jwt.ExpiredSignatureError):
            self._decode(token)

    def test_token_invalido_firma_incorrecta(self):
        forged = jwt.encode(
            {"sub": "ana", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "otra-clave",
            algorithm=ALGORITHM,
        )
        with self.assertRaises(jwt.JWTError):
            self._decode(forged)

    def test_token_basura(self):
        with self.assertRaises(jwt.JWTError):
            self._decode("no-es-un-jwt")


class RateLimitTest(unittest.TestCase):
    def test_limite_ventana_y_reinicio(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        with mock.patch("middleware.rate_limit.datetime") as dt:
            dt.now.return_value = t0
            self.assertTrue(rl.check_rate_limit("a"))
            self.assertTrue(rl.check_rate_limit("a"))
            self.assertFalse(rl.check_rate_limit("a"))  # limite
            self.assertTrue(rl.check_rate_limit("b"))  # otra llave independiente
            dt.now.return_value = t0 + timedelta(seconds=61)
            self.assertTrue(rl.check_rate_limit("a"))  # ventana vencida: reinicio


if __name__ == "__main__":
    unittest.main()
