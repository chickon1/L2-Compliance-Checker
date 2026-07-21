import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from compliance_checker.models import CredentialProfile, Device, Platform, Site
from compliance_checker.repository import Repository


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.key = Fernet.generate_key().decode()
        self.repository = Repository(db_path, credential_key=self.key)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_credential_profile_round_trip(self) -> None:
        profile = CredentialProfile(id="p1", name="lab", username="admin")
        self.repository.add_credential_profile(profile, password="s3cret")

        profiles = self.repository.list_credential_profiles()
        self.assertEqual([p.id for p in profiles], ["p1"])

        credentials = self.repository.get_credentials("p1")
        self.assertEqual(credentials.username, "admin")
        self.assertEqual(credentials.password, "s3cret")

    def test_credential_profile_requires_key(self) -> None:
        repository = Repository(
            str(Path(self._tmpdir.name) / "nokey.db"), credential_key=None
        )
        profile = CredentialProfile(id="p1", name="lab", username="admin")
        with self.assertRaises(RuntimeError):
            repository.add_credential_profile(profile, password="s3cret")

    def test_device_add_and_list(self) -> None:
        device = Device(
            id="d1",
            name="sw1",
            management_address="192.168.100.11",
            platform=Platform.CISCO_IOS,
            site="Lab",
            credential_profile_id="p1",
        )
        self.repository.add_device(device)

        devices = self.repository.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0], device)
        self.assertEqual(self.repository.get_device("d1"), device)

    def test_site_lookup_by_name(self) -> None:
        site = Site(id="s1", name="GNS3 Lab")
        self.repository.add_site(site)

        self.assertEqual(self.repository.get_site_by_name("GNS3 Lab"), site)
        self.assertIsNone(self.repository.get_site_by_name("Nowhere"))
        self.assertEqual([s.name for s in self.repository.list_sites()], ["GNS3 Lab"])


if __name__ == "__main__":
    unittest.main()
