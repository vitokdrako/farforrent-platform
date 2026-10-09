"""
Test CORS configuration for the new domain `farforevent.com.ua`.
Also regression-check existing domains and the cabinet-profile data-leak fix.
"""
import os
import requests
import pytest

BASE_URL = "http://localhost:8001"
LOGIN_PATH = "/api/event/auth/login"
HEALTH_PATH = "/api/event/health"
PROFILE_PATH = "/api/event/cabinet/profile"

NEW_ORIGINS = [
    "https://farforevent.com.ua",
    "https://www.farforevent.com.ua",
    "http://farforevent.com.ua",
    "http://www.farforevent.com.ua",
]
EXISTING_ORIGINS = [
    "https://rentalhub.farforrent.com.ua",
    "https://item-photos.preview.emergentagent.com",
]
BAD_ORIGIN = "https://evil-domain.example.com"


# --- Health ---
def test_health_endpoint_ok():
    r = requests.get(f"{BASE_URL}{HEALTH_PATH}", timeout=10)
    assert r.status_code == 200


def _preflight(origin: str):
    return requests.options(
        f"{BASE_URL}{LOGIN_PATH}",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=10,
    )


# --- New domain CORS preflight checks ---
@pytest.mark.parametrize("origin", NEW_ORIGINS)
def test_cors_preflight_new_domain(origin):
    r = _preflight(origin)
    assert r.status_code == 200, f"Got {r.status_code} for origin {origin} -- body: {r.text!r}"
    assert r.headers.get("access-control-allow-origin") == origin, (
        f"Expected allow-origin={origin}, got {r.headers.get('access-control-allow-origin')!r}"
    )
    assert r.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in r.headers.get("access-control-allow-methods", "")


# --- Existing domains regression ---
@pytest.mark.parametrize("origin", EXISTING_ORIGINS)
def test_cors_preflight_existing_domain(origin):
    r = _preflight(origin)
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials") == "true"


# --- Disallowed origin ---
def test_cors_preflight_disallowed_origin():
    r = _preflight(BAD_ORIGIN)
    # The header MUST NOT echo back the bad origin
    assert r.headers.get("access-control-allow-origin") != BAD_ORIGIN


# --- Regression: cabinet profile data-leak fix still holds ---
def test_login_and_cabinet_profile_match():
    login = requests.post(
        f"{BASE_URL}{LOGIN_PATH}",
        json={"email": "vitokdrako@gmail.com", "password": "test123"},
        timeout=15,
    )
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.text}"
    token = login.json().get("access_token")
    assert token, "No access_token in login response"

    prof = requests.get(
        f"{BASE_URL}{PROFILE_PATH}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert prof.status_code == 200
    assert prof.json().get("email") == "vitokdrako@gmail.com"
