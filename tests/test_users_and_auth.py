import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from compliance_checker.auth import SESSION_COOKIE_NAME
from compliance_checker.bootstrap import _build_app
from compliance_checker.collectors.mock import MockConfigCollector
from compliance_checker.models import Role, User
from compliance_checker.repository import Repository


class UserCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        self.admin = User(id="u1", username="alice", role=Role.ADMIN)
        self.repository.add_user(self.admin, "hunter2")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_verify_login_round_trip(self) -> None:
        self.assertEqual(self.repository.verify_login("alice", "hunter2").id, "u1")
        self.assertIsNone(self.repository.verify_login("alice", "wrong"))
        self.assertIsNone(self.repository.verify_login("nobody", "hunter2"))

    def test_get_user_by_username(self) -> None:
        self.assertEqual(self.repository.get_user_by_username("alice").id, "u1")
        self.assertIsNone(self.repository.get_user_by_username("nobody"))

    def test_update_username_and_role_keeps_password(self) -> None:
        self.repository.add_user(User(id="u2", username="bob", role=Role.ADMIN), "pw")
        self.repository.update_user("u1", "alice2", Role.USER, None)
        self.assertEqual(self.repository.get_user("u1").username, "alice2")
        self.assertEqual(self.repository.get_user("u1").role, Role.USER)
        self.assertEqual(self.repository.verify_login("alice2", "hunter2").id, "u1")

    def test_update_password(self) -> None:
        self.repository.update_user("u1", "alice", Role.ADMIN, "newpass")
        self.assertIsNotNone(self.repository.verify_login("alice", "newpass"))
        self.assertIsNone(self.repository.verify_login("alice", "hunter2"))

    def test_update_missing_user_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.repository.update_user("nope", "x", Role.USER, None)

    def test_cannot_demote_last_admin(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.update_user("u1", "alice", Role.USER, None)

    def test_can_demote_admin_when_another_admin_remains(self) -> None:
        self.repository.add_user(User(id="u2", username="bob", role=Role.ADMIN), "pw")
        self.repository.update_user("u1", "alice", Role.USER, None)  # should not raise
        self.assertEqual(self.repository.get_user("u1").role, Role.USER)

    def test_cannot_delete_last_admin(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.delete_user("u1")

    def test_delete_missing_user_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.repository.delete_user("nope")

    def test_delete_user_clears_sessions(self) -> None:
        self.repository.add_user(User(id="u2", username="bob", role=Role.USER), "pw")
        token = self.repository.create_session("u2")
        self.repository.delete_user("u2")
        self.assertIsNone(self.repository.get_session_user(token))


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        self.repository.add_user(User(id="u1", username="alice", role=Role.ADMIN), "pw")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_and_resolve_session(self) -> None:
        token = self.repository.create_session("u1")
        self.assertEqual(self.repository.get_session_user(token).id, "u1")

    def test_unknown_token_returns_none(self) -> None:
        self.assertIsNone(self.repository.get_session_user("not-a-real-token"))

    def test_deleted_session_returns_none(self) -> None:
        token = self.repository.create_session("u1")
        self.repository.delete_session(token)
        self.assertIsNone(self.repository.get_session_user(token))

    def test_expired_session_returns_none(self) -> None:
        token = self.repository.create_session("u1")
        with patch("compliance_checker.repository.datetime") as mock_datetime:
            # Only patch now(); fromisoformat must still work on real strings.
            import datetime as real_datetime

            mock_datetime.now.return_value = real_datetime.datetime.now(
                real_datetime.timezone.utc
            ) + real_datetime.timedelta(days=31)
            mock_datetime.fromisoformat.side_effect = real_datetime.datetime.fromisoformat
            self.assertIsNone(self.repository.get_session_user(token))


class AuthApiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        app = _build_app(MockConfigCollector(), self.repository)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_status_reports_setup_required_before_any_user_exists(self) -> None:
        status = self.client.get("/api/v1/auth/status").json()
        self.assertTrue(status["setup_required"])
        self.assertFalse(status["authenticated"])

    def test_protected_route_requires_login(self) -> None:
        response = self.client.get("/api/v1/devices")
        self.assertEqual(response.status_code, 401)

    def test_setup_creates_admin_and_logs_in(self) -> None:
        response = self.client.post(
            "/api/v1/auth/setup", json={"username": "alice", "password": "hunter2"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "admin")
        self.assertIn(SESSION_COOKIE_NAME, response.cookies)

        # now authenticated -- the previously-401ing route should work
        self.assertEqual(self.client.get("/api/v1/devices").status_code, 200)

    def test_setup_only_works_once(self) -> None:
        self.client.post("/api/v1/auth/setup", json={"username": "alice", "password": "hunter2"})
        second = self.client.post(
            "/api/v1/auth/setup", json={"username": "mallory", "password": "whatever"}
        )
        self.assertEqual(second.status_code, 409)

    def test_login_with_wrong_password_rejected(self) -> None:
        self.client.post("/api/v1/auth/setup", json={"username": "alice", "password": "hunter2"})
        self.client.post("/api/v1/auth/logout")
        response = self.client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_clears_session(self) -> None:
        self.client.post("/api/v1/auth/setup", json={"username": "alice", "password": "hunter2"})
        self.client.post("/api/v1/auth/logout")
        self.assertEqual(self.client.get("/api/v1/devices").status_code, 401)

    def test_non_admin_cannot_manage_users(self) -> None:
        self.client.post("/api/v1/auth/setup", json={"username": "alice", "password": "hunter2"})
        self.client.post(
            "/api/v1/users", json={"username": "bob", "password": "pw", "role": "user"}
        )
        self.client.post("/api/v1/auth/logout")
        self.client.post("/api/v1/auth/login", json={"username": "bob", "password": "pw"})

        self.assertEqual(self.client.get("/api/v1/users").status_code, 403)


if __name__ == "__main__":
    unittest.main()
