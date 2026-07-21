import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from compliance_checker.models import CredentialProfile, Device, Platform
from compliance_checker.repository import Repository


class DeviceCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repository = Repository(str(Path(self._tmpdir.name) / "test.db"))
        self.device = Device(
            id="dev1", name="sw1", management_address="10.0.0.1", platform=Platform.CISCO_IOS
        )
        self.repository.add_device(self.device)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_update_device(self) -> None:
        updated = self.device.model_copy(update={"name": "sw1-renamed", "site": "HQ"})
        self.repository.update_device(updated)

        stored = self.repository.get_device("dev1")
        self.assertEqual(stored.name, "sw1-renamed")
        self.assertEqual(stored.site, "HQ")

    def test_update_missing_device_raises(self) -> None:
        missing = Device(
            id="nope", name="x", management_address="10.0.0.9", platform=Platform.CISCO_IOS
        )
        with self.assertRaises(KeyError):
            self.repository.update_device(missing)

    def test_delete_device(self) -> None:
        self.repository.delete_device("dev1")
        with self.assertRaises(KeyError):
            self.repository.get_device("dev1")

    def test_delete_missing_device_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.repository.delete_device("nope")

    def test_delete_device_clears_its_overrides(self) -> None:
        self.repository.set_override("dev1", "rule1", "waived", datetime.now(timezone.utc))
        self.repository.delete_device("dev1")
        self.repository.add_device(self.device)  # re-add same id
        self.assertEqual(self.repository.get_overrides_by_device("dev1"), {})


class CredentialProfileCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.key = Fernet.generate_key().decode()
        self.repository = Repository(
            str(Path(self._tmpdir.name) / "test.db"), credential_key=self.key
        )
        self.profile = CredentialProfile(id="p1", name="lab", username="admin")
        self.repository.add_credential_profile(self.profile, "s3cret")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_update_name_and_username_keeps_password(self) -> None:
        self.repository.update_credential_profile("p1", "lab-renamed", "root", None)

        profiles = {p.id: p for p in self.repository.list_credential_profiles()}
        self.assertEqual(profiles["p1"].name, "lab-renamed")
        self.assertEqual(profiles["p1"].username, "root")
        self.assertEqual(self.repository.get_credentials("p1").password, "s3cret")

    def test_update_password(self) -> None:
        self.repository.update_credential_profile("p1", "lab", "admin", "newpass")
        self.assertEqual(self.repository.get_credentials("p1").password, "newpass")

    def test_update_missing_profile_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.repository.update_credential_profile("nope", "x", "y", None)

    def test_delete_credential_profile(self) -> None:
        self.repository.delete_credential_profile("p1")
        self.assertEqual(self.repository.list_credential_profiles(), [])

    def test_delete_missing_profile_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.repository.delete_credential_profile("nope")


if __name__ == "__main__":
    unittest.main()
