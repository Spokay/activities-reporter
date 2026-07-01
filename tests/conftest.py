import base64
import time
from typing import Any

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from database.engine import init_engine

ISSUER = "https://auth.spokayhub.top/realms/spokay-realm"
AUDIENCE = "activities-reporter"
KID = "test-kid"


def _b64url_int(n: int) -> str:
    n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def _rsa_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


@pytest.fixture(scope="session")
def fake_jwks(_rsa_key) -> dict[str, Any]:
    pub = _rsa_key.public_key().public_numbers()
    return {
        "keys": [{
            "kty": "RSA",
            "kid": KID,
            "use": "sig",
            "alg": "RS256",
            "n": _b64url_int(pub.n),
            "e": _b64url_int(pub.e),
        }]
    }


@pytest.fixture(scope="session")
def _private_pem(_rsa_key) -> bytes:
    return _rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(scope="session")
def make_token(_private_pem):
    def _make(
        *,
        issuer: str = ISSUER,
        audience: str = AUDIENCE,
        exp_offset: int = 3600,
        kid: str = KID,
    ) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "sub": "test-user",
                "iss": issuer,
                "aud": audience,
                "iat": now,
                "exp": now + exp_offset,
            },
            _private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )
    return _make


@pytest.fixture
def valid_token(make_token) -> str:
    return make_token()


@pytest.fixture(scope="session", autouse=True)
def init_db():
    init_engine()
