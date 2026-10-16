"""Phase 2: Supabase JWT auth, per-user time zones, the dev clock, and return-range config."""
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import update

from app import auth, clock
from app.auth import dev_user_id
from app.config import Settings, get_settings
from app.models import Catch, Message, User

pytestmark = pytest.mark.usefixtures("clean")

TEXT = "A message long enough to pass the twenty character minimum."
SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long"
SUPABASE_URL = "https://example-ref.supabase.co"
ISSUER = SUPABASE_URL + "/auth/v1"


@pytest.fixture(autouse=True)
def supabase(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "supabase_url", SUPABASE_URL)
    monkeypatch.setattr(s, "supabase_jwt_secret", SECRET)
    yield s


@pytest.fixture(autouse=True)
def real_time():
    yield
    clock._offset = timedelta(0)


def token(sub=None, *, aud="authenticated", iss=ISSUER, exp_in=3600, key=SECRET, alg="HS256", headers=None, **extra):
    now = int(time.time())
    claims = {"sub": str(sub or uuid.uuid4()), "aud": aud, "iss": iss, "iat": now, "exp": now + exp_in,
              "role": "authenticated", **extra}
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


def bearer(tok, **more):
    return {"Authorization": f"Bearer {tok}", **more}


# ---- JWT verification ---------------------------------------------------------

def test_valid_token_signs_in_and_creates_the_user(client, db):
    uid = uuid.uuid4()
    r = client.get("/api/me", headers=bearer(token(uid)))
    assert r.status_code == 200, r.text
    assert r.json()["free_catches"] == get_settings().free_catches_per_day
    assert db.get(User, uid) is not None


def test_expired_token_is_rejected(client):
    r = client.get("/api/me", headers=bearer(token(exp_in=-120)))  # past the 30s leeway
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_wrong_audience_is_rejected(client):
    assert client.get("/api/me", headers=bearer(token(aud="anon"))).status_code == 401
    assert client.get("/api/me", headers=bearer(token(aud="something-else"))).status_code == 401


def test_wrong_issuer_signature_or_missing_sub_is_rejected(client):
    assert client.get("/api/me", headers=bearer(token(iss="https://evil.supabase.co/auth/v1"))).status_code == 401
    assert client.get("/api/me", headers=bearer(token(key="another-secret-that-is-also-32-bytes-long"))).status_code == 401
    no_sub = jwt.encode({"aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60}, SECRET, "HS256")
    assert client.get("/api/me", headers=bearer(no_sub)).status_code == 401
    assert client.get("/api/me", headers=bearer("not-a-jwt")).status_code == 401


def test_unsigned_token_is_rejected(client):
    claims = {"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60}
    assert client.get("/api/me", headers=bearer(jwt.encode(claims, None, algorithm="none"))).status_code == 401


def test_hs256_is_refused_without_a_configured_secret(client, supabase, monkeypatch):
    monkeypatch.setattr(supabase, "supabase_jwt_secret", "")
    assert client.get("/api/me", headers=bearer(token())).status_code == 401


class _FakeJwks:
    def __init__(self, public_key, kid):
        self.public_key, self.kid = public_key, kid

    def get_signing_key_from_jwt(self, tok):
        if jwt.get_unverified_header(tok).get("kid") != self.kid:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return jwt.PyJWK.from_dict({**jwt.algorithms.ECAlgorithm.to_jwk(self.public_key, as_dict=True),
                                    "kid": self.kid, "alg": "ES256"})


def test_asymmetric_tokens_are_checked_against_the_project_jwks(client, monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    seen_urls = []

    def fake_client(url):
        seen_urls.append(url)
        return _FakeJwks(private.public_key(), "key-1")

    monkeypatch.setattr(auth, "_jwks_client", fake_client)
    good = token(key=private, alg="ES256", headers={"kid": "key-1"})
    assert client.get("/api/me", headers=bearer(good)).status_code == 200
    assert seen_urls[0] == ISSUER + "/.well-known/jwks.json"

    unknown_kid = token(key=private, alg="ES256", headers={"kid": "key-2"})
    assert client.get("/api/me", headers=bearer(unknown_kid)).status_code == 401
    other = ec.generate_private_key(ec.SECP256R1())
    forged = token(key=other, alg="ES256", headers={"kid": "key-1"})
    assert client.get("/api/me", headers=bearer(forged)).status_code == 401
    expired = token(key=private, alg="ES256", headers={"kid": "key-1"}, exp_in=-120)
    assert client.get("/api/me", headers=bearer(expired)).status_code == 401


def test_dev_header_only_works_in_dev_mode(client, supabase, monkeypatch):
    assert client.get("/api/me", headers={"X-Dev-User": "asha"}).status_code == 200
    monkeypatch.setattr(supabase, "dev_mode", False)
    assert client.get("/api/me", headers={"X-Dev-User": "asha"}).status_code == 401
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=bearer(token())).status_code == 200


def test_bad_bearer_does_not_fall_back_to_the_dev_header(client):
    r = client.get("/api/me", headers=bearer(token(exp_in=-120), **{"X-Dev-User": "asha"}))
    assert r.status_code == 401


# ---- time zones ---------------------------------------------------------------

def test_browser_time_zone_is_stored_on_first_sign_in_only(client, db):
    uid = uuid.uuid4()
    tok = token(uid)
    r = client.get("/api/me", headers=bearer(tok, **{"X-Timezone": "America/Los_Angeles"}))
    assert r.json()["tz"] == "America/Los_Angeles"
    r = client.get("/api/me", headers=bearer(tok, **{"X-Timezone": "Europe/London"}))
    assert r.json()["tz"] == "America/Los_Angeles"
    assert db.get(User, uid).tz == "America/Los_Angeles"


@pytest.mark.parametrize("bad", ["Not/AZone", "../../etc/passwd", "America", ""])
def test_unknown_time_zone_falls_back_to_default(client, bad):
    r = client.get("/api/me", headers=bearer(token(), **{"X-Timezone": bad}))
    assert r.status_code == 200
    assert r.json()["tz"] == get_settings().default_tz


def test_refill_happens_at_midnight_in_the_users_own_zone(client, db, monkeypatch):
    uid = uuid.uuid4()
    headers = bearer(token(uid), **{"X-Timezone": "America/Los_Angeles"})
    # 16 Oct 2026 06:59 UTC is 23:59 on 15 Oct in Los Angeles (PDT, UTC-7) but 12:29 on 16 Oct in Kolkata.
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 10, 16, 6, 59, tzinfo=timezone.utc))
    assert client.get("/api/me", headers=headers).status_code == 200
    user = db.get(User, uid)
    assert user.free_refilled_on.isoformat() == "2026-10-15"  # local date, not the server's or Kolkata's
    db.execute(update(User).where(User.id == uid).values(free_catches=0))
    db.commit()

    assert client.get("/api/me", headers=headers).json()["free_catches"] == 0
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 10, 16, 7, 1, tzinfo=timezone.utc))
    assert client.get("/api/me", headers=headers).json()["free_catches"] == get_settings().free_catches_per_day


# ---- dev clock ----------------------------------------------------------------

def dev(client, name="asha"):
    h = {"X-Dev-User": name}
    return lambda method, path, json=None: client.request(method, "/api" + path, json=json, headers=h)


def test_dev_clock_moves_now_and_resets(client):
    call = dev(client)
    before = datetime.fromisoformat(call("GET", "/dev/clock").json()["now"])
    r = call("POST", "/dev/clock", {"add_days": 30}).json()
    assert r["offset_days"] == 30
    assert datetime.fromisoformat(r["now"]) - before >= timedelta(days=30)
    assert call("POST", "/dev/clock", {"add_days": 1}).json()["offset_days"] == 31
    assert call("POST", "/dev/clock", {"reset": True}).json()["offset_days"] == 0
    assert call("POST", "/dev/clock", {"add_days": -1}).status_code == 422


def test_dev_clock_is_refused_outside_dev_mode(client, supabase, monkeypatch):
    monkeypatch.setattr(supabase, "dev_mode", False)
    h = bearer(token())
    assert client.post("/api/dev/clock", json={"add_days": 1}, headers=h).status_code == 404
    assert client.get("/api/dev/clock", headers=h).status_code == 404
    assert client.post("/api/dev/force-due", headers=h).status_code == 404
    with pytest.raises(PermissionError):
        clock.set_offset(timedelta(days=1))
    assert clock.offset() == timedelta(0)


def test_skipping_a_day_refills_catches_and_writes(client, db):
    call = dev(client)
    call("GET", "/me")
    db.execute(update(User).where(User.id == dev_user_id("asha")).values(free_catches=0, writes_today=3))
    db.commit()
    assert call("GET", "/me").json()["free_catches"] == 0
    call("POST", "/dev/clock", {"add_days": 1})
    me = call("GET", "/me").json()
    assert me["free_catches"] == get_settings().free_catches_per_day
    assert me["writes_left"] == get_settings().writes_per_day
    # Going back to real time must not freeze refills on a "future" date.
    call("POST", "/dev/clock", {"reset": True})
    db.execute(update(User).where(User.id == dev_user_id("asha")).values(free_catches=0))
    db.commit()
    assert call("GET", "/me").json()["free_catches"] == get_settings().free_catches_per_day


def test_skipping_years_brings_messages_back_and_timestamps_follow_the_clock(client, db):
    a, b = dev(client, "asha"), dev(client, "bilal")
    call = a
    call("POST", "/dev/clock", {"add_days": 10})
    shifted = clock.now()
    mid = uuid.UUID(a("POST", "/messages", {"text": TEXT, "return_option": "far"}).json()["id"])
    assert b("POST", "/catch").json()["id"] == str(mid)

    msg = db.get(Message, mid)
    caught = db.get(Catch, (dev_user_id("bilal"), mid))
    for ts in (msg.created_at, caught.caught_at, db.get(User, dev_user_id("asha")).created_at):
        assert abs(ts - shifted) < timedelta(minutes=1), "server defaults must follow the dev clock"

    assert a("POST", "/catch").json() == {"type": "river_empty"}
    call("POST", "/dev/clock", {"add_days": 365 * 5})  # past the longest range
    reveal = a("POST", "/catch").json()
    assert reveal["type"] == "reveal" and reveal["id"] == str(mid)
    assert datetime.fromisoformat(reveal["written_at"]) - shifted < timedelta(minutes=1)
    assert a("POST", f"/messages/{mid}/keep").status_code == 204
    returned = a("GET", "/yours").json()["returned"][0]
    assert datetime.fromisoformat(returned["returned_at"]) - clock.now() < timedelta(minutes=1)


# ---- cooling period and range config ------------------------------------------

def test_cooling_period_wins_over_a_range_configured_below_it(client, db, supabase, monkeypatch):
    monkeypatch.setattr(supabase, "return_ranges", {"near": (1, 5), "any": (0, 0), "far": (10, 20)})
    call = dev(client)
    call("POST", "/dev/refill")
    for option in ("near", "any", "far"):
        mid = call("POST", "/messages", {"text": f"{TEXT} {option}", "return_option": option}).json()["id"]
        m = db.get(Message, uuid.UUID(mid))
        days = (m.return_at - m.created_at) / timedelta(days=1)
        assert supabase.cooling_days <= days, (option, days)
        assert days <= supabase.cooling_days + 1e-6, (option, days)  # range collapses to the cooling day

    # And nothing comes back after 29 days.
    call("POST", "/dev/clock", {"add_days": supabase.cooling_days - 1})
    assert call("POST", "/catch").json()["type"] != "reveal"
    call("POST", "/dev/clock", {"add_days": 1})
    assert call("POST", "/catch").json()["type"] == "reveal"


def test_ranges_and_cooling_are_env_configurable(monkeypatch):
    monkeypatch.setenv("RIVER_COOLING_DAYS", "45")
    monkeypatch.setenv("RIVER_RETURN_RANGES", '{"near": [45, 60], "any": [45, 400], "far": [500, 900]}')
    s = Settings()
    assert s.cooling_days == 45
    assert s.return_ranges == {"near": (45, 60), "any": (45, 400), "far": (500, 900)}


@pytest.mark.parametrize("ranges", [
    '{"near": [90, 30], "any": [30, 1095], "far": [730, 1825]}',
    '{"near": [-1, 30], "any": [30, 1095], "far": [730, 1825]}',
    '{"soon": [30, 60]}',
])
def test_malformed_ranges_are_rejected_at_startup(monkeypatch, ranges):
    monkeypatch.setenv("RIVER_RETURN_RANGES", ranges)
    with pytest.raises(ValueError):
        Settings()
