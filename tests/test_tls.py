import ssl
import sys
import unittest
from unittest import mock

from aicl import tls


class TlsTests(unittest.TestCase):
    def setUp(self):
        tls._context = None

    def tearDown(self):
        tls._context = None

    def test_context_verifies_and_is_reused(self):
        ctx = tls.context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        self.assertIs(tls.context(), ctx)

    def test_without_certifi_the_system_store_is_enough(self):
        with mock.patch.dict(sys.modules, {"certifi": None}):
            ctx = tls.context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_urlopen_passes_the_context(self):
        seen = {}

        def fake(req, timeout=None, context=None):
            seen.update(req=req, timeout=timeout, context=context)
            return "resp"
        with mock.patch("urllib.request.urlopen", fake):
            self.assertEqual(tls.urlopen("https://example.org", timeout=5), "resp")
        self.assertIs(seen["context"], tls.context())
        self.assertEqual(seen["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
