import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.core.auth import (
    generate_api_key,
    hash_api_key,
    key_prefix,
    extract_bearer_token,
    get_current_tenant,
    API_KEY_PREFIX,
)
from fastapi import HTTPException


def test_generate_api_key_is_unique_and_prefixed():
    k1, k2 = generate_api_key(), generate_api_key()
    assert k1.startswith(API_KEY_PREFIX)
    assert k1 != k2
    assert len(k1) > 20


def test_hash_is_stable_and_not_the_raw_key():
    k = generate_api_key()
    assert hash_api_key(k) == hash_api_key(k)
    assert hash_api_key(k) != k
    assert len(hash_api_key(k)) == 64  # sha256 hex


def test_key_prefix_is_non_secret_leading_chars():
    k = generate_api_key()
    assert k.startswith(key_prefix(k))
    assert len(key_prefix(k)) == 12


@pytest.mark.parametrize("header", [None, "", "Token abc", "Bearer", "Bearer "])
def test_extract_bearer_rejects_bad_headers(header):
    with pytest.raises(HTTPException) as exc:
        extract_bearer_token(header)
    assert exc.value.status_code == 401


def test_extract_bearer_accepts_valid_header():
    assert extract_bearer_token("Bearer ask_123") == "ask_123"


# --- dependency tests with a stubbed DB session ---------------------------- #

class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, tenant):
        self._tenant = tenant

    async def execute(self, *_args, **_kwargs):
        return _Result(self._tenant)


def test_get_current_tenant_returns_tenant_for_valid_key():
    sentinel = object()
    tenant = asyncio.run(get_current_tenant(authorization="Bearer ask_valid", db=_FakeDB(sentinel)))
    assert tenant is sentinel


def test_get_current_tenant_401_for_unknown_key():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_tenant(authorization="Bearer ask_unknown", db=_FakeDB(None)))
    assert exc.value.status_code == 401


def test_get_current_tenant_401_for_missing_header():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_tenant(authorization=None, db=_FakeDB(object())))
    assert exc.value.status_code == 401
