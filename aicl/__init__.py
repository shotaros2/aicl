"""AICL — a language for agent-to-agent communication (reference implementation)."""

from .model import (
    ACTS, Agent, Date, Duration, Form, Instant, Keyword, KList, KMap, AICLError,
    LexError, Message, ModelError, ParseError, Quantity, Ref, ReplyRef, Route,
    Str, Symbol, Var, is_message, walk,
)
from .parser import parse, parse_messages, parse_one
from .printer import canonical, canonical_document, digest, pretty, to_text
from .json_codec import dumps as to_json_text, loads as from_json_text, to_json, from_json
from .cbor_codec import to_cbor, from_cbor
from .dense import to_dense, from_dense, dense_document
from .codebook import Codebook
from .validate import Issue, nl_ratio, validate_conversation, validate_message

__version__ = "0.2.0"

__all__ = [
    "ACTS", "Agent", "Date", "Duration", "Form", "Instant", "Keyword", "KList", "KMap",
    "AICLError", "LexError", "Message", "ModelError", "ParseError", "Quantity", "Ref",
    "ReplyRef", "Route", "Str", "Symbol", "Var", "is_message", "walk",
    "parse", "parse_messages", "parse_one",
    "canonical", "canonical_document", "digest", "pretty", "to_text",
    "to_json_text", "from_json_text", "to_json", "from_json", "to_cbor", "from_cbor",
    "to_dense", "from_dense", "dense_document", "Codebook",
    "Issue", "nl_ratio", "validate_conversation", "validate_message",
    "__version__",
]
