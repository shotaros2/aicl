"""Tokenizer-aware codebooks (SPEC §8.1).

A codebook maps each *concept id* (a canonical AICL symbol such as
`photorealistic`) to alternative *surface forms* (`photo`, `写実`). The sender
picks, per concept, the form that costs the fewest tokens on the receiver's
tokenizer; the receiver maps every form back to the concept id before it
interprets anything. Four rules keep this free of ambiguity:

1. The canonical form (validation, hashing, logs) uses concept ids only.
2. A surface form belongs to exactly one concept, and is never itself a concept id.
3. A form that is not in the codebook is an unknown term (`clar`), never guessed.
4. The receiver's tokenizer is agreed explicitly, never assumed.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable, Dict, List, Optional

from . import tokens
from .dense import CODE_KEY, KEY_CODE, expand as dense_expand, to_dense
from .lexer import _TOKEN, classify_atom
from .model import CORE_HEADS, Form, Keyword, KList, KMap, LexError, ModelError, Symbol, Term
from .parser import parse
from .printer import to_text

RESERVED_WORDS = {"true", "false", "null"}
FORM_RE = re.compile(r'^[^\s()\[\]{}";<>=]+$')
SIGILS = "@#^$:~!"

Counter = Callable[[str], int]


class Codebook:
    def __init__(self, concepts: Dict[str, List[str]], name: str = "", published_id: str = ""):
        self.name = name
        self.published_id = published_id      # e.g. "aicl.sched.1" for a standard codebook (SPEC §8.2)
        self.concepts: Dict[str, List[str]] = {}
        self.form_to_concept: Dict[str, str] = {}
        self.warnings: List[str] = []
        for cid, forms in concepts.items():
            self._check_concept(cid)
            kept = []
            for f in forms:
                if f == cid:
                    continue
                self._check_form(f, cid)
                if _is_truncation(f, cid):
                    self.warnings.append(
                        f"form {f!r} of {cid!r} is a truncation that reads as an ordinary word; "
                        f"small models tend to leave such forms unexpanded (see evals/)")
                if f in concepts:
                    raise ModelError(f"form {f!r} is also a concept id")
                owner = self.form_to_concept.get(f)
                if owner is not None and owner != cid:
                    raise ModelError(f"form {f!r} belongs to both {owner!r} and {cid!r}")
                self.form_to_concept[f] = cid
                kept.append(f)
            self.concepts[cid] = kept

    # ------------------------------------------------------------ validation

    @staticmethod
    def _check_concept(cid: str) -> None:
        try:
            atom = classify_atom(cid)
        except LexError as e:
            raise ModelError(f"concept id {cid!r}: {e}") from None
        if not isinstance(atom, Symbol):
            raise ModelError(f"concept id {cid!r} is not a symbol")
        if cid in CORE_HEADS or cid in KEY_CODE or cid in CODE_KEY or (len(cid) == 1 and cid.isupper()):
            raise ModelError(f"concept id {cid!r} is reserved core vocabulary")

    @staticmethod
    def _check_form(f: str, cid: str) -> None:
        bad = (
            not FORM_RE.match(f) or f[0] in SIGILS or f in RESERVED_WORDS
            or (len(f) == 1 and f.isascii())          # single ASCII letters are dense codes
            or f in CORE_HEADS or f in KEY_CODE
        )
        if bad:
            raise ModelError(f"form {f!r} of {cid!r} is reserved or malformed")
        try:
            atom = classify_atom(f)
        except LexError:
            return  # e.g. non-ASCII: fine, it is replaced before lexing
        if not isinstance(atom, Symbol):
            raise ModelError(f"form {f!r} of {cid!r} would read as {type(atom).__name__}")

    # --------------------------------------------------------------- loading

    @classmethod
    def load(cls, path: str) -> "Codebook":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "concepts" not in data:
            raise ModelError("codebook file must be a JSON object with a 'concepts' key")
        pid = data.get("id", "")
        if pid:
            atom = classify_atom(pid)
            if not isinstance(atom, Symbol):
                raise ModelError(f"codebook id {pid!r} is not an AICL symbol")
        return cls(data["concepts"], data.get("name", ""), pid)

    @property
    def id(self) -> str:
        """Content hash shared by both agents to confirm they hold the same table."""
        canon = json.dumps(self.concepts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------- selection

    def choose(self, counter: Optional[Counter] = None) -> Dict[str, str]:
        """Cheapest form per concept for `counter` (default: aicl.tokens.count)."""
        counter = counter or tokens.count
        best = {}
        for cid, forms in self.concepts.items():
            cands = [cid] + forms
            # fewest tokens; ties: the concept id itself, then shortest, then lexicographic
            best[cid] = min(cands, key=lambda f: (counter(" " + f), f != cid, len(f), f))
        return best

    # ------------------------------------------------------------------ pack

    def pack(self, term: Term, counter: Optional[Counter] = None, best: Optional[Dict[str, str]] = None) -> Term:
        """Copy of `term` with concept ids replaced by their cheapest forms."""
        best = best if best is not None else self.choose(counter)
        return _rename(term, best)

    def pack_text(self, term: Term, counter: Optional[Counter] = None, dense: bool = True) -> str:
        packed = self.pack(term, counter)
        return to_dense(packed) if dense else to_text(packed)

    # ---------------------------------------------------------------- unpack

    def unpack_text(self, text: str) -> str:
        """Rewrite every surface form in raw text back to its concept id."""
        out = []
        for m in _TOKEN.finditer(text):
            kind, raw = m.lastgroup, m.group()
            if kind in ("ws", "comment"):
                continue
            if kind == "atom":
                if raw in self.form_to_concept:
                    raw = self.form_to_concept[raw]
                elif raw.startswith(":") and raw[1:] in self.form_to_concept:
                    raw = ":" + self.form_to_concept[raw[1:]]
            out.append(raw)
        return " ".join(out)

    def unpack(self, text: str) -> List[Term]:
        """Parse packed text (dense or readable) into canonical terms."""
        return parse(dense_expand(self.unpack_text(text)))

    def unresolved_forms(self, text: str) -> List[str]:
        """Non-ASCII or otherwise unlexable atoms left after unpacking: rule 3 violations."""
        bad = []
        for m in _TOKEN.finditer(dense_expand(self.unpack_text(text))):
            if m.lastgroup == "atom":
                try:
                    classify_atom(m.group())
                except LexError:
                    bad.append(m.group())
        return bad


def _is_truncation(form: str, cid: str) -> bool:
    """Lower-case ASCII prefix of the concept id (deploy < deploy-status, roll < rollout, err < error-rate)."""
    if not form.isascii() or not form.islower() or len(form) >= len(cid):
        return False
    head = cid.split("-")[0].split(".")[0]
    return cid.startswith(form) or head.startswith(form)


def _rename(term: Term, best: Dict[str, str]) -> Term:
    if isinstance(term, Symbol):
        return Symbol(best.get(term.name, term.name))
    if isinstance(term, Keyword):
        return Keyword(best.get(term.name, term.name))
    if isinstance(term, Form):
        return Form(best.get(term.head, term.head),
                    [_rename(a, best) for a in term.args],
                    {best.get(k, k): _rename(v, best) for k, v in term.kw.items()},
                    term.conf)
    if isinstance(term, KList):
        return KList([_rename(a, best) for a in term.items])
    if isinstance(term, KMap):
        return KMap([(_rename(k, best), _rename(v, best)) for k, v in term.items])
    return term
