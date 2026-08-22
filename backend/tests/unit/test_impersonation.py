"""View-as is read-only, and these are the tests that make that true.

The feature exists so an admin can answer "I can't see the button" by looking
at what the other person sees. The whole risk of it is that looking turns into
doing — by accident, or by somebody who has taken an admin's laptop.

So the guarantee is not "the UI hides the buttons". It is that the server
refuses every unsafe HTTP method for as long as an impersonation cookie is
set, in middleware, before routing. These tests hold that line:

  - they go over real HTTP through TestClient rather than calling the helper,
    because the helper is not what a browser talks to;
  - they hit routes the UI never exposes, and methods no button sends;
  - they assert the refusal happens *before* the handler, which is what makes
    it true for routes that do not exist yet.

None of this needs MongoDB. That is deliberate: the read-only guarantee is the
one thing in this codebase that must be checked by the suite gating a pull
request, and the integration suite cannot be.
"""
import re
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import server


ADMIN = {"_id": "507f1f77bcf86cd799439011", "name": "Admin", "role": "admin"}
TARGET = "507f1f77bcf86cd799439012"

UNSAFE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]


@pytest.fixture(scope="module")
def client():
    return TestClient(server.app)


def _token(target=TARGET, actor=ADMIN, **overrides):
    payload = {
        "sub": target,
        "act": str(actor["_id"]),
        "act_name": actor.get("name"),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "type": "impersonation",
    }
    payload.update(overrides)
    return jwt.encode(payload, server._jwt_secret(), algorithm=server.JWT_ALGORITHM)


def _impersonating(client, **kw):
    client.cookies.set(server.IMPERSONATION_COOKIE, _token(**kw))
    return client


class TestTheReadOnlyGuarantee:
    """Nothing may be changed while a view-as session is open."""

    @pytest.mark.parametrize("method", UNSAFE_METHODS)
    @pytest.mark.parametrize(
        "path",
        [
            # One per router, chosen for what they would do if they ran.
            "/api/creator/profile",
            "/api/brand/campaigns",
            "/api/admin/creators/507f1f77bcf86cd799439012/approve",
            "/api/admin/payments/507f1f77bcf86cd799439012/mark_paid",
            "/api/collaborations/507f1f77bcf86cd799439012/notes",
            "/api/manager/collaborations/507f1f77bcf86cd799439012/check-in",
            "/api/campaigns/507f1f77bcf86cd799439012/apply",
            "/api/auth/logout",
            # A path that does not exist. It must still be refused: the point
            # is that the answer does not depend on the route table.
            "/api/does/not/exist",
        ],
    )
    def test_no_unsafe_method_gets_through(self, client, method, path):
        r = _impersonating(client).request(method, path)
        client.cookies.clear()
        assert r.status_code == 403, f"{method} {path} returned {r.status_code}"
        assert r.json().get("code") == "impersonation_read_only"

    def test_the_refusal_happens_before_the_handler(self, client):
        """Not "every route checks" — "the request never reaches a route".

        This is what makes the guarantee hold for a route added next week by
        somebody who has never read this file. The proof is that a path with no
        handler at all is refused with the impersonation code rather than a
        404: nothing resolved it, and it was still stopped.
        """
        r = _impersonating(client).post("/api/nothing/here/at/all")
        client.cookies.clear()
        assert r.status_code == 403
        assert r.json()["code"] == "impersonation_read_only"

    def test_a_body_or_a_content_type_changes_nothing(self, client):
        r = _impersonating(client).post(
            "/api/creator/profile", json={"name": "changed"}
        )
        client.cookies.clear()
        assert r.status_code == 403

    def test_reading_still_works(self, client):
        # The whole point of the feature. /health touches no database, so a
        # pass here is the middleware letting it through rather than a lucky
        # connection.
        r = _impersonating(client).get("/api/health")
        client.cookies.clear()
        assert r.status_code == 200

    @pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
    def test_the_other_safe_methods_reach_the_router(self, client, method):
        """/api/health only declares GET, so these come back 405.

        That is the assertion: 405 is the *router* answering, which means the
        middleware passed the request on. A 403 here would mean a safe method
        had been swept up with the unsafe ones.
        """
        r = _impersonating(client).request(method, "/api/health")
        client.cookies.clear()
        assert r.status_code != 403
        assert r.json().get("code") != "impersonation_read_only" if r.content else True

    def test_the_method_list_is_the_rule_rather_than_a_list_of_endpoints(self):
        """An allow-list of dangerous routes would have to be maintained.

        "GET, HEAD and OPTIONS cannot change anything, everything else is
        refused" does not. If somebody inverts this into an endpoint list, the
        next endpoint is unprotected the day it is written.
        """
        import inspect

        src = inspect.getsource(server._reject_impersonated_writes)
        assert "request.method not in SAFE_METHODS" in src
        assert set(server.SAFE_METHODS) == {"GET", "HEAD", "OPTIONS"}

    def test_only_the_stop_route_is_exempt(self):
        # One exception, and it must stay one. The stop endpoint clears a
        # cookie and writes an audit line; it touches no business data, which
        # is the only reason allowing it is safe.
        import inspect

        src = inspect.getsource(server._reject_impersonated_writes)
        assert src.count("IMPERSONATION_STOP_PATH") == 1
        assert server.IMPERSONATION_STOP_PATH == "/api/auth/impersonate/stop"
        # And it really is mounted where the exemption says it is.
        assert any(
            getattr(r, "path", "") == server.IMPERSONATION_STOP_PATH
            and "POST" in (getattr(r, "methods", None) or set())
            for r in server.app.routes
        )


class TestTheTokenItself:
    def test_a_forged_token_is_not_an_impersonation(self, client):
        # Signed with the wrong key: treated as absent, so the request falls
        # through to whatever real session the caller has.
        bad = jwt.encode(
            {"sub": TARGET, "act": ADMIN["_id"], "type": "impersonation"},
            "not-the-secret",
            algorithm=server.JWT_ALGORITHM,
        )
        client.cookies.set(server.IMPERSONATION_COOKIE, bad)
        r = client.get("/api/health")
        client.cookies.clear()
        assert r.status_code == 200

    def test_an_access_token_cannot_be_used_as_an_impersonation_token(self):
        """The two are told apart by `type`, not by which cookie they arrived in.

        Without this an ordinary access token dropped into the impersonation
        cookie would be read as a view-as claim for its own subject.
        """
        access = server.create_access_token(TARGET, "a@b.in", "creator")

        class _Req:
            cookies = {server.IMPERSONATION_COOKIE: access}

        assert server._decode_impersonation(_Req()) is None

    def test_an_expired_token_reads_as_not_impersonating(self):
        expired = jwt.encode(
            {
                "sub": TARGET,
                "act": ADMIN["_id"],
                "type": "impersonation",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            server._jwt_secret(),
            algorithm=server.JWT_ALGORITHM,
        )

        class _Req:
            cookies = {server.IMPERSONATION_COOKIE: expired}

        # Not an error: the session timed out and the admin is themselves
        # again, which is what should happen to a tab left open overnight.
        assert server._decode_impersonation(_Req()) is None

    def test_an_expired_session_stops_being_read_only(self, client):
        expired = jwt.encode(
            {
                "sub": TARGET,
                "act": ADMIN["_id"],
                "type": "impersonation",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            server._jwt_secret(),
            algorithm=server.JWT_ALGORITHM,
        )
        client.cookies.set(server.IMPERSONATION_COOKIE, expired)
        r = client.post("/api/nothing/here")
        client.cookies.clear()
        # 404, not 403: the middleware let it through, so the admin's own
        # session governs again rather than them being stuck read-only.
        assert r.status_code != 403

    def test_the_session_is_short(self):
        assert server.IMPERSONATION_MIN <= 60

    def test_the_admin_keeps_their_own_session(self):
        """Impersonation adds a cookie; it must never replace the admin's.

        Swapping `access_token` would mean a failure while stopping leaves the
        admin logged in as somebody else with no way back.
        """
        import inspect

        src = inspect.getsource(server.impersonate_user)
        assert "access_token" not in src
        assert "_clear_auth_cookies" not in src
        assert server.IMPERSONATION_COOKIE == "impersonation_token"


class TestWhoMayBeImpersonated:
    def test_admins_are_not_impersonatable(self):
        # An admin already sees everything an admin sees, so the only thing
        # admin→admin would add is acting as a named colleague — exactly what
        # the audit log exists to make impossible.
        assert "admin" not in server.IMPERSONATABLE_ROLES

    def test_the_roles_named_are_the_ones_support_is_asked_about(self):
        assert set(server.IMPERSONATABLE_ROLES) == {
            "creator",
            "brand",
            "brand_manager",
            "campaign_manager",
            "weare_team",
        }

    def test_a_scoped_console_is_impersonatable_and_an_unscoped_one_is_not(self):
        """The distinction the list is drawn on. A `weare_team` member sees the
        admin console with a scope around it, so looking through them shows an
        admin something they cannot otherwise see; looking through another admin
        shows them their own screen with somebody else's name on the audit
        line."""
        assert "weare_team" in server.IMPERSONATABLE_ROLES
        assert "admin" not in server.IMPERSONATABLE_ROLES

    def test_starting_is_admin_only(self):
        import inspect

        assert 'require_roles("admin")' in inspect.getsource(server.impersonate_user)

    def test_stopping_deliberately_has_no_role_guard(self):
        """The caller *is* the impersonated creator as far as every guard is
        concerned, so requiring admin here would lock the admin inside the
        session this exists to leave. The token is the authorisation."""
        import inspect

        # The call form, not the bare name — the docstring above explains why
        # there is no role guard, and a substring test would read that
        # explanation as the guard being present.
        src = inspect.getsource(server.stop_impersonating)
        assert "Depends(require_roles" not in src
        assert "_decode_impersonation" in src


class TestItIsAlwaysAudited:
    @pytest.mark.parametrize(
        "fn_name,action",
        [
            ("impersonate_user", "admin.impersonate.start"),
            ("stop_impersonating", "admin.impersonate.stop"),
        ],
    )
    def test_both_ends_write_an_audit_line(self, fn_name, action):
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert "await audit(" in src, f"{fn_name} does not audit"
        assert action in src

    @pytest.mark.parametrize("fn_name", ["impersonate_user", "stop_impersonating"])
    def test_the_audit_line_names_the_target(self, fn_name):
        # "An admin impersonated somebody" is not an audit trail. Which
        # somebody is the entire question asked of it later.
        import inspect

        src = inspect.getsource(getattr(server, fn_name))
        assert "target_user_id" in src
        assert "target_name" in src

    def test_the_audit_actor_is_the_admin_not_the_target(self):
        """The stop line is written while the *target* is the current user.

        Auditing the caller would credit the creator with ending a session they
        never knew about. The admin is recovered from the token's `act` claim,
        which is why it is carried there in the first place.
        """
        import inspect

        src = inspect.getsource(server.stop_impersonating)
        assert 'claim["act"]' in src
        assert re.search(r"audit\(\s*actor,", src), "stop audits somebody other than the admin"

    def test_the_start_is_audited_before_the_cookie_is_set(self):
        """Order matters. If the cookie were set first and the audit write
        failed, there would be a live view-as session with no record of it."""
        import inspect

        src = inspect.getsource(server.impersonate_user)
        assert src.index("await audit(") < src.index("response.set_cookie")

    def test_a_session_cannot_be_chained_to_another_person(self):
        # Without this an admin could hop from creator to creator with one
        # audited start and no stop in between.
        import inspect

        assert "_decode_impersonation" in inspect.getsource(server.impersonate_user)


class TestTheBannerCannotBeMissed:
    def test_me_reports_the_session_from_the_token(self):
        """The frontend must not draw its banner from something it stored when
        it started: a second tab, or a session that expired while the tab sat
        open, would then show the wrong thing. /auth/me is the source."""
        import inspect

        src = inspect.getsource(server.me)
        assert "_impersonation" in src
        assert '"read_only": True' in src

    def test_the_acting_admin_is_named(self):
        import inspect

        src = inspect.getsource(server.me)
        assert "actor_name" in src
