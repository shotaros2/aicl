import tempfile
import unittest
from pathlib import Path

import aicl
from aicl.blob import blob_hash, file_hash, make_blob, verify_blob


class BlobTests(unittest.TestCase):
    def test_make_verify_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.png"
            p.write_bytes(b"not really a png")
            b = make_blob(p, uri="https://cdn.example/x.png")
            self.assertEqual(b.kw["bytes"], 16)
            self.assertEqual(b.kw["media"].text, "image/png")
            self.assertTrue(verify_blob(p, b))
            self.assertEqual(blob_hash(b), file_hash(p))
            # the form survives the text round trip and still verifies
            again = aicl.parse_one(aicl.to_text(b))
            self.assertTrue(verify_blob(p, again))
            # changed content no longer matches its name
            p.write_bytes(b"not really a png!")
            self.assertFalse(verify_blob(p, b))

    def test_blob_hash_rejects_malformed(self):
        self.assertIsNone(blob_hash(aicl.parse_one("(blob sha256:abc)")))
        self.assertIsNone(blob_hash(aicl.parse_one("(blob \"" + "0" * 64 + "\")")))


if __name__ == "__main__":
    unittest.main()
