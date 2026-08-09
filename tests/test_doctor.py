import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from metagate.doctor import check_url


class DoctorTest(unittest.TestCase):
    def test_http_error_still_proves_endpoint_is_reachable(self):
        error = HTTPError("http://datahub.test/graphql", 400, "bad probe", {}, None)
        with patch("metagate.doctor.urlopen", side_effect=error):
            ok, detail = check_url("http://datahub.test/graphql")
        self.assertTrue(ok)
        self.assertEqual(detail, "reachable (HTTP 400)")

    def test_network_failure_is_reported_as_not_ready(self):
        with patch("metagate.doctor.urlopen", side_effect=OSError("connection refused")):
            ok, detail = check_url("http://127.0.0.1:8765/healthz", method="GET")
        self.assertFalse(ok)
        self.assertIn("connection refused", detail)

    def test_doctor_source_marks_optional_checks_separately(self):
        from pathlib import Path
        import metagate.doctor

        source = Path(metagate.doctor.__file__).read_text(encoding="utf-8")
        self.assertIn('"required": False', source)
        self.assertIn('"required_ready": required_ready', source)


if __name__ == "__main__":
    unittest.main()
