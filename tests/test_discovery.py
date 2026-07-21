import unittest

from compliance_checker.collectors.discovery import _parse_range


class ParseRangeTests(unittest.TestCase):
    def test_cidr_excludes_network_and_broadcast(self) -> None:
        addresses = _parse_range("192.168.100.0/30")
        self.assertEqual(addresses, ["192.168.100.1", "192.168.100.2"])

    def test_full_start_end_range(self) -> None:
        addresses = _parse_range("192.168.100.1-192.168.100.3")
        self.assertEqual(
            addresses, ["192.168.100.1", "192.168.100.2", "192.168.100.3"]
        )

    def test_short_form_start_end_range(self) -> None:
        addresses = _parse_range("192.168.100.10-12")
        self.assertEqual(
            addresses, ["192.168.100.10", "192.168.100.11", "192.168.100.12"]
        )

    def test_single_address(self) -> None:
        self.assertEqual(_parse_range("192.168.100.5"), ["192.168.100.5"])


if __name__ == "__main__":
    unittest.main()
