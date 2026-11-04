"""Minimal deterministic CBOR (RFC 8949 §4.2) for the AICL JSON model.

Supports exactly what the JSON model needs: null, booleans, integers, floats,
UTF-8 strings, arrays and string-keyed maps. No dependencies.
"""
from __future__ import annotations

import math
import struct

from .json_codec import from_json, to_json
from .model import ModelError, Term


def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    if n < 0x100:
        return bytes([(major << 5) | 24, n])
    if n < 0x10000:
        return bytes([(major << 5) | 25]) + struct.pack(">H", n)
    if n < 0x1_0000_0000:
        return bytes([(major << 5) | 26]) + struct.pack(">I", n)
    if n < 0x1_0000_0000_0000_0000:
        return bytes([(major << 5) | 27]) + struct.pack(">Q", n)
    raise ModelError("integer too large for CBOR")


def _encode_float(x: float) -> bytes:
    if math.isnan(x) or math.isinf(x):
        raise ModelError("non-finite float")
    for fmt, code in ((">e", 0xF9), (">f", 0xFA)):
        try:
            packed = struct.pack(fmt, x)
        except (OverflowError, struct.error):
            continue
        if struct.unpack(fmt, packed)[0] == x:
            return bytes([code]) + packed
    return b"\xfb" + struct.pack(">d", x)


def encode(obj) -> bytes:
    if obj is None:
        return b"\xf6"
    if obj is True:
        return b"\xf5"
    if obj is False:
        return b"\xf4"
    if isinstance(obj, int):
        return _head(0, obj) if obj >= 0 else _head(1, -1 - obj)
    if isinstance(obj, float):
        return _encode_float(obj)
    if isinstance(obj, str):
        b = obj.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(obj, (list, tuple)):
        return _head(4, len(obj)) + b"".join(encode(a) for a in obj)
    if isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            if not isinstance(k, str):
                raise ModelError("CBOR map keys must be strings")
            items.append((encode(k), encode(v)))
        items.sort(key=lambda kv: kv[0])  # bytewise lexicographic (RFC 8949 §4.2.1)
        return _head(5, len(items)) + b"".join(k + v for k, v in items)
    raise ModelError(f"cannot CBOR-encode {type(obj).__name__}")


class _Decoder:
    def __init__(self, data: bytes):
        self.data = data
        self.i = 0

    def _take(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise ModelError("truncated CBOR")
        chunk = self.data[self.i:self.i + n]
        self.i += n
        return chunk

    def _arg(self, info: int) -> int:
        if info < 24:
            return info
        if info == 24:
            return self._take(1)[0]
        if info == 25:
            return struct.unpack(">H", self._take(2))[0]
        if info == 26:
            return struct.unpack(">I", self._take(4))[0]
        if info == 27:
            return struct.unpack(">Q", self._take(8))[0]
        raise ModelError("indefinite-length items are not allowed")

    def item(self):
        b = self._take(1)[0]
        major, info = b >> 5, b & 0x1F
        if major == 0:
            return self._arg(info)
        if major == 1:
            return -1 - self._arg(info)
        if major == 3:
            return self._take(self._arg(info)).decode("utf-8")
        if major == 4:
            return [self.item() for _ in range(self._arg(info))]
        if major == 5:
            out = {}
            for _ in range(self._arg(info)):
                k = self.item()
                if not isinstance(k, str):
                    raise ModelError("CBOR map keys must be strings")
                out[k] = self.item()
            return out
        if major == 7:
            if info == 20:
                return False
            if info == 21:
                return True
            if info == 22:
                return None
            if info == 25:
                return struct.unpack(">e", self._take(2))[0]
            if info == 26:
                return struct.unpack(">f", self._take(4))[0]
            if info == 27:
                return struct.unpack(">d", self._take(8))[0]
        raise ModelError(f"unsupported CBOR item 0x{b:02x}")


def decode(data: bytes):
    d = _Decoder(data)
    obj = d.item()
    if d.i != len(data):
        raise ModelError("trailing bytes after CBOR item")
    return obj


def to_cbor(term: Term) -> bytes:
    return encode(to_json(term))


def from_cbor(data: bytes) -> Term:
    return from_json(decode(data))
