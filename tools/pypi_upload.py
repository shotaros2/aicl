"""Upload the built package to PyPI using PYPI_TOKEN from .env.

    python tools/pypi_upload.py            # build check + upload dist/*
    python tools/pypi_upload.py --check    # only validate the files, no upload

Installs twine if missing. Forces UTF-8 output (twine's rich console crashes
on cp932 Windows consoles otherwise). The token is never printed.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aicl.env import load_dotenv  # noqa: E402


def run(args, env=None):
    r = subprocess.run([sys.executable, "-m", "twine", *args], env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    tok = (env or {}).get("TWINE_PASSWORD")
    if tok:
        out = out.replace(tok, "***")
    print(out.strip()[-2000:])
    return r.returncode


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    files = sorted(glob.glob(str(ROOT / "dist" / "*")))
    if not files:
        print("dist/ is empty: run  python -m build  first")
        return 1
    try:
        import twine  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "twine"], check=True)
    base_env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", TERM="dumb", NO_COLOR="1")
    if run(["check", *files], base_env) != 0:
        return 1
    if "--check" in argv:
        return 0
    token = os.environ.get("PYPI_TOKEN", "")
    if not token.startswith("pypi-"):
        print("PYPI_TOKEN is missing from .env (it must start with 'pypi-')")
        return 1
    env = dict(base_env, TWINE_USERNAME="__token__", TWINE_PASSWORD=token, TWINE_NON_INTERACTIVE="1")
    code = run(["upload", "--disable-progress-bar", "--skip-existing", *files], env)
    print("upload " + ("succeeded: https://pypi.org/project/aicl-lang/" if code == 0 else "failed"))
    return code


if __name__ == "__main__":
    sys.exit(main())
