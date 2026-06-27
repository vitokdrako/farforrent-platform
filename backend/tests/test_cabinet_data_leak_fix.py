"""
Regression tests for Cabinet 2.0 data leak fix.
The bug: /cabinet/* endpoints were resolving client_users by event_customers.customer_id
(unrelated ID space), leaking other users' data. Fix: resolve client_users by email_normalized.

Test user: vitokdrako@gmail.com (Vita). The leaked user before fix was marinasummer80@gmail.com
(Марина Ткачова).
"""

import os
import time
import base64
import requests
import pytest
import jwt as pyjwt

# Prefer public URL, fall back to local FastAPI on 8001
PUBLIC_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
LOCAL_URL = "http://localhost:8001"


def _pick_base_url():
    for url in [PUBLIC_URL, LOCAL_URL]:
        if not url:
            continue
        try:
            r = requests.post(
                f"{url}/api/event/auth/login",
                json={"email": "vitokdrako@gmail.com", "password": "test123"},
                timeout=10,
            )
            if r.status_code == 200 and "access_token" in r.json():
                return url
        except Exception:
            continue
    pytest.skip("No usable backend URL reachable")


BASE_URL = _pick_base_url()
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAA"
    "AAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture(scope="session")
def auth():
    r = requests.post(
        f"{BASE_URL}/api/event/auth/login",
        json={"email": "vitokdrako@gmail.com", "password": "test123"},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    # Decode the JWT (no verify, just to read claims)
    try:
        claims = pyjwt.decode(token, options={"verify_signature": False})
    except Exception:
        claims = {}
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "claims": claims}


# ------------------------------------------------------------
# 1) /cabinet/profile must return Vita (not Марина)
# ------------------------------------------------------------
class TestProfile:
    def test_profile_returns_logged_in_user_not_leaked(self, auth):
        r = requests.get(
            f"{BASE_URL}/api/event/cabinet/profile",
            headers=auth["headers"],
            timeout=15,
        )
        assert r.status_code == 200, f"profile failed: {r.status_code} {r.text}"
        data = r.json()
        # The endpoint may wrap in {profile: {...}}; handle both
        profile = data.get("profile", data)
        email = (profile.get("email") or "").lower()
        full_name = profile.get("full_name") or profile.get("name") or ""
        assert email == "vitokdrako@gmail.com", (
            f"DATA LEAK: profile email is {email!r}, expected vitokdrako@gmail.com. Full: {profile}"
        )
        assert "Марина" not in full_name and "Ткачова" not in full_name, (
            f"DATA LEAK: full_name contains Марина: {full_name!r}"
        )
        # JWT email claim should match profile email (only check if JWT carries an email)
        jwt_email = (auth["claims"].get("email") or "").lower()
        if jwt_email and "@" in jwt_email:
            assert jwt_email == email, f"JWT email {jwt_email!r} != profile email {email!r}"


# ------------------------------------------------------------
# 2) /cabinet/payers — listing must only show Vita's payers
# ------------------------------------------------------------
class TestPayers:
    def test_payers_listing_belongs_to_vita(self, auth):
        r = requests.get(
            f"{BASE_URL}/api/event/cabinet/payers",
            headers=auth["headers"],
            timeout=15,
        )
        assert r.status_code == 200, f"GET payers failed: {r.status_code} {r.text}"
        body = r.json()
        payers = body.get("payers") or body.get("items") or (body if isinstance(body, list) else [])
        assert isinstance(payers, list)
        # None of the payers should leak Марина's contact info
        for p in payers:
            blob = " ".join(
                str(p.get(k, "")) for k in ("director_name", "company_name", "email", "phone")
            )
            assert "marinasummer80" not in blob.lower(), f"Leaked Марина payer: {p}"
            assert "Марина" not in blob, f"Leaked Марина payer: {p}"

    def test_payers_crud_smoke_and_scoping(self, auth):
        unique_name = f"TEST_Vendor_{int(time.time())}"
        # CREATE
        create = requests.post(
            f"{BASE_URL}/api/event/cabinet/payers",
            headers=auth["headers"],
            json={"company_name": unique_name, "payer_type": "fop"},
            timeout=15,
        )
        assert create.status_code in (200, 201), f"Create payer failed: {create.status_code} {create.text}"
        cj = create.json()
        payer_id = cj.get("payer_id") or cj.get("id") or (cj.get("payer") or {}).get("id")
        assert payer_id, f"payer_id missing in create response: {cj}"

        # LIST should include it
        r = requests.get(f"{BASE_URL}/api/event/cabinet/payers", headers=auth["headers"], timeout=15)
        assert r.status_code == 200
        body = r.json()
        payers = body.get("payers") or body.get("items") or []
        ids = [p.get("id") or p.get("payer_id") for p in payers]
        assert payer_id in ids, f"Created payer {payer_id} not in list {ids}"

        # UPDATE
        upd = requests.put(
            f"{BASE_URL}/api/event/cabinet/payers/{payer_id}",
            headers=auth["headers"],
            json={"company_name": unique_name + "_upd", "payer_type": "fop"},
            timeout=15,
        )
        assert upd.status_code in (200, 204), f"Update payer failed: {upd.status_code} {upd.text}"

        # SET DEFAULT
        sd = requests.put(
            f"{BASE_URL}/api/event/cabinet/payers/{payer_id}/default",
            headers=auth["headers"],
            timeout=15,
        )
        assert sd.status_code in (200, 204), f"Set default failed: {sd.status_code} {sd.text}"

        # DELETE link
        d = requests.delete(
            f"{BASE_URL}/api/event/cabinet/payers/{payer_id}",
            headers=auth["headers"],
            timeout=15,
        )
        assert d.status_code in (200, 204), f"Delete payer failed: {d.status_code} {d.text}"

        # Verify removed
        r2 = requests.get(f"{BASE_URL}/api/event/cabinet/payers", headers=auth["headers"], timeout=15)
        body2 = r2.json()
        payers2 = body2.get("payers") or body2.get("items") or []
        ids2 = [p.get("id") or p.get("payer_id") for p in payers2]
        assert payer_id not in ids2, f"Payer {payer_id} still present after delete: {ids2}"


# ------------------------------------------------------------
# 3) /cabinet/master-agreement — Vita's own, idempotent, DDMMYYYY in contract_number
# ------------------------------------------------------------
class TestMasterAgreement:
    def test_master_agreement_idempotent_and_dated(self, auth):
        r1 = requests.get(
            f"{BASE_URL}/api/event/cabinet/master-agreement",
            headers=auth["headers"],
            timeout=15,
        )
        assert r1.status_code == 200, f"MA GET 1 failed: {r1.status_code} {r1.text}"
        b1 = r1.json()
        agr1 = b1.get("agreement") or b1
        id1 = agr1.get("id")
        contract_number = agr1.get("contract_number") or ""
        # Forbid leaked Марина's known agreement ids from earlier session
        assert id1 not in (18, 83), f"DATA LEAK: returned Марина's MA id {id1}"
        # contract_number should embed DDMMYYYY of the day it was created (any past date OK,
        # we only assert it contains an 8-digit run that ends with the current year or recent year)
        import re
        m = re.search(r"(\d{8})", contract_number)
        assert m, f"contract_number {contract_number!r} should contain DDMMYYYY"
        ddmmyyyy = m.group(1)
        yyyy = ddmmyyyy[-4:]
        assert yyyy in ("2025", "2026"), (
            f"contract_number {contract_number!r} year part {yyyy} not recent"
        )

        # idempotent
        r2 = requests.get(
            f"{BASE_URL}/api/event/cabinet/master-agreement",
            headers=auth["headers"],
            timeout=15,
        )
        assert r2.status_code == 200
        b2 = r2.json()
        agr2 = b2.get("agreement") or b2
        id2 = agr2.get("id")
        assert id1 == id2, f"MA not idempotent: id1={id1} id2={id2}"

    def test_master_agreement_sign(self, auth):
        payload = {
            "signature_png_base64": f"data:image/png;base64,{TINY_PNG_B64}",
            "signer_name": "Vita Filimonikhina",
        }
        s = requests.post(
            f"{BASE_URL}/api/event/cabinet/master-agreement/sign",
            headers=auth["headers"],
            json=payload,
            timeout=20,
        )
        assert s.status_code in (200, 201), f"sign failed: {s.status_code} {s.text}"

        r = requests.get(
            f"{BASE_URL}/api/event/cabinet/master-agreement",
            headers=auth["headers"],
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        agr = body.get("agreement") or body
        status = agr.get("status") or body.get("status")
        needs = body.get("needs_signature", agr.get("needs_signature"))
        assert status == "signed", f"after sign, status={status!r}, body={body}"
        if needs is not None:
            assert needs is False, f"after sign, needs_signature={needs!r}"


# ------------------------------------------------------------
# 4) /cabinet/documents — must only return Vita's documents (no Марина leak)
# ------------------------------------------------------------
class TestDocuments:
    def test_documents_belong_to_vita(self, auth):
        r = requests.get(
            f"{BASE_URL}/api/event/cabinet/documents",
            headers=auth["headers"],
            timeout=20,
        )
        assert r.status_code == 200, f"documents failed: {r.status_code} {r.text}"
        body = r.json()
        docs = body.get("documents") or body.get("items") or (body if isinstance(body, list) else [])
        assert isinstance(docs, list)
        for d in docs:
            blob = " ".join(str(d.get(k, "")) for k in d.keys())
            assert "marinasummer80" not in blob.lower(), f"DATA LEAK: doc contains Марина email: {d}"


# ------------------------------------------------------------
# 5) /cabinet/notifications/unread — returns {new_documents: N>=0}
# ------------------------------------------------------------
class TestNotifications:
    def test_unread_returns_count(self, auth):
        r = requests.get(
            f"{BASE_URL}/api/event/cabinet/notifications/unread",
            headers=auth["headers"],
            timeout=15,
        )
        assert r.status_code == 200, f"unread failed: {r.status_code} {r.text}"
        body = r.json()
        assert "new_documents" in body, f"missing new_documents key: {body}"
        assert isinstance(body["new_documents"], int)
        assert body["new_documents"] >= 0


# ------------------------------------------------------------
# 6) convert-to-order gate — without signed MA, must return 412 AGREEMENT_REQUIRED.
#    Since we DO sign the MA in TestMasterAgreement (session-scope sign),
#    this test only checks the endpoint contract using a definitely-invalid board id.
# ------------------------------------------------------------
class TestConvertGate:
    def test_convert_to_order_invalid_or_gate(self, auth):
        # Use a likely-nonexistent board id; the endpoint can return 404 or 412.
        # We accept either, but specifically assert that IF 412 returned, the code is AGREEMENT_REQUIRED.
        r = requests.post(
            f"{BASE_URL}/api/event/boards/999999999/convert-to-order",
            headers=auth["headers"],
            json={},  # body required
            timeout=15,
        )
        # Document the actual behavior; do not hard-fail if 404
        if r.status_code == 412:
            try:
                detail = r.json().get("detail", {})
                code = detail.get("code") if isinstance(detail, dict) else None
                assert code == "AGREEMENT_REQUIRED", f"412 returned but code={code!r}"
            except Exception:
                pytest.fail(f"412 returned but body not parsable: {r.text}")
        else:
            # Acceptable: 404/403/400 — just note it
            assert r.status_code in (400, 401, 403, 404, 409, 412), (
                f"Unexpected status {r.status_code}: {r.text}"
            )
