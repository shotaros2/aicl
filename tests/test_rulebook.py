import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_rulebook  # tools/build_rulebook.py


class RulebookTests(unittest.TestCase):
    def test_rulebook_folder_matches_sources(self):
        problems = build_rulebook.stale()
        self.assertEqual(problems, [], "rulebook/ is stale; run: python tools/build_rulebook.py")

    def test_rulebook_is_self_contained(self):
        names = {p.relative_to(ROOT / "rulebook").as_posix() for p in (ROOT / "rulebook").rglob("*") if p.is_file()}
        for required in ("README.md", "koine-rulebook.md", "koine-rulebook-dense.md", "SPEC.md",
                         "codebooks/bench.json", "examples/01_weather.koine"):
            self.assertIn(required, names)


if __name__ == "__main__":
    unittest.main()
