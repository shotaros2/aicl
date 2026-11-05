import io
import json
import os
import unittest
import urllib.error
from contextlib import contextmanager

from aicl import muse, vendors


def fake_opener(reply="(tell #b.1 @b>@a ^a.1 {$t 18.5C})", status=200, seen=None):
    @contextmanager
    def opener(req, timeout=0):
        if seen is not None:
            seen.append((req.full_url, dict(req.header_items()), json.loads(req.data.decode("utf-8"))))
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "nope", {}, io.BytesIO(b'{"error":"region"}'))
        yield io.BytesIO(json.dumps({"choices": [{"message": {"role": "assistant", "content": reply}}]}).encode())
    return opener


class MuseTests(unittest.TestCase):
    def test_request_shape_and_reply(self):
        seen = []
        ask = muse.text_ask(api_key="k", opener=fake_opener(seen=seen))
        out = ask("SYSTEM", [{"role": "user", "content": "(ask #a.1 @a>@b (temp :loc tokyo) $t)"}])
        self.assertEqual(out, "(tell #b.1 @b>@a ^a.1 {$t 18.5C})")
        url, headers, body = seen[0]
        self.assertEqual(url, "https://api.meta.ai/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer k")
        self.assertEqual(body["model"], "muse-spark-1.1")
        self.assertEqual(body["messages"][0], {"role": "developer", "content": "SYSTEM"})
        self.assertEqual(body["messages"][1]["role"], "user")
        self.assertEqual(body["temperature"], 0)

    def test_other_openai_compatible_endpoint(self):
        seen = []
        ask = muse.text_ask(model="x-1", base_url="http://localhost:11434/v1/", api_key="k",
                            system_role="system", opener=fake_opener(seen=seen))
        ask("S", [])
        self.assertEqual(seen[0][0], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(seen[0][2]["messages"], [{"role": "system", "content": "S"}])

    def test_403_names_the_region_restriction(self):
        ask = muse.text_ask(api_key="k", opener=fake_opener(status=403))
        with self.assertRaises(muse.AccessDenied) as cm:
            ask("S", [])
        self.assertIn("US only", str(cm.exception))

    def test_missing_key_is_a_clear_error(self):
        self.assertNotIn("MODEL_API_KEY_TEST_UNSET", os.environ)
        with self.assertRaises(RuntimeError) as cm:
            muse.text_ask(key_env="MODEL_API_KEY_TEST_UNSET")
        self.assertIn("MODEL_API_KEY_TEST_UNSET", str(cm.exception))

    def test_vendor_registry(self):
        self.assertEqual(vendors.VENDORS, ("claude", "gemini", "muse"))
        self.assertEqual(vendors.describe("muse"), "muse (muse-spark-1.1)")
        with self.assertRaises(ValueError):
            vendors.text_ask("llama")


if __name__ == "__main__":
    unittest.main()
