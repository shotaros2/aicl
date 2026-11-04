"""Recursive-descent parser: text -> terms / messages."""
from __future__ import annotations

from typing import List

from .lexer import ConfTok, Punct, Token, tokenize
from .model import Form, Keyword, KList, KMap, Message, ParseError, Symbol, Term

_CLOSE = {"(": ")", "[": "]", "{": "}"}


class _Parser:
    def __init__(self, text: str):
        self.toks: List[Token] = list(tokenize(text))
        self.i = 0

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def _next(self) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError("unexpected end of input")
        self.i += 1
        return tok

    def _is_punct(self, tok, ch) -> bool:
        return tok is not None and isinstance(tok.value, Punct) and tok.value.char == ch

    def term(self) -> Term:
        tok = self._next()
        v = tok.value
        if isinstance(v, Punct):
            if v.char == "(":
                return self._form(tok)
            if v.char == "[":
                return self._list(tok)
            if v.char == "{":
                return self._map(tok)
            raise ParseError(f"unexpected '{v.char}' at {tok.line}:{tok.col}")
        if isinstance(v, ConfTok):
            raise ParseError(f"confidence marker outside a form at {tok.line}:{tok.col}")
        return v

    def _form(self, open_tok: Token) -> Form:
        head_tok = self._next()
        if not isinstance(head_tok.value, Symbol):
            raise ParseError(f"form head must be a symbol at {head_tok.line}:{head_tok.col}")
        form = Form(head_tok.value.name)
        while True:
            tok = self._peek()
            if tok is None:
                raise ParseError(f"unclosed '(' opened at {open_tok.line}:{open_tok.col}")
            if self._is_punct(tok, ")"):
                self.i += 1
                return form
            if isinstance(tok.value, Keyword):
                self.i += 1
                nxt = self._peek()
                if nxt is None or self._is_punct(nxt, ")"):
                    raise ParseError(f"keyword :{tok.value.name} has no value at {tok.line}:{tok.col}")
                if tok.value.name in form.kw:
                    raise ParseError(f"duplicate keyword :{tok.value.name} at {tok.line}:{tok.col}")
                form.kw[tok.value.name] = self.term()
            elif isinstance(tok.value, ConfTok):
                self.i += 1
                if form.conf is not None:
                    raise ParseError(f"duplicate confidence marker at {tok.line}:{tok.col}")
                form.conf = tok.value.value
            else:
                form.args.append(self.term())

    def _seq(self, open_tok: Token, close: str) -> list:
        items = []
        while True:
            tok = self._peek()
            if tok is None:
                raise ParseError(f"unclosed '{open_tok.value.char}' opened at {open_tok.line}:{open_tok.col}")
            if self._is_punct(tok, close):
                self.i += 1
                return items
            items.append(self.term())

    def _list(self, open_tok: Token) -> KList:
        return KList(self._seq(open_tok, "]"))

    def _map(self, open_tok: Token) -> KMap:
        items = self._seq(open_tok, "}")
        if len(items) % 2:
            raise ParseError(f"map opened at {open_tok.line}:{open_tok.col} has an odd number of elements")
        return KMap([(items[i], items[i + 1]) for i in range(0, len(items), 2)])

    def document(self) -> List[Term]:
        out = []
        while self._peek() is not None:
            out.append(self.term())
        return out


def parse(text: str) -> List[Term]:
    """Parse a document into a list of top-level terms."""
    return _Parser(text).document()


def parse_one(text: str) -> Term:
    terms = parse(text)
    if len(terms) != 1:
        raise ParseError(f"expected exactly one term, found {len(terms)}")
    return terms[0]


def parse_messages(text: str) -> List[Message]:
    """Parse a document whose top-level terms are all messages."""
    return [Message.from_form(t) for t in parse(text)]
