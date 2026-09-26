"""Google News ids are url-safe base64 protobufs; this module builds and
reads the ones the API needs (validated 2026-09-26).

  topic        CAAq… = {1:0, 5:{1:10, 4:<b64 inner>, 10:1}}
                 inner {1:16, 2:{1:"/m/09nm_", 2:"en", 3:"US"}, 5:0}   a Knowledge Graph topic
                 inner {1:18, 2:{1:12, 13:{1:"cnn.com"}}, 5:0}          a publication (any domain)
                 inner {1:18, 2:{7:"story-360", 9:{…}}, 5:0}             a story (opaque)
                 inner {1:18, 2:{7:"local_v2"}, 5:0}                     "Your local news"
  section      CAQ…  = {1:4, 5:<the topic outer message> | …}           a tab of a topic
  article      CBMi… / CAIi…                                           opaque

A publication id can therefore be BUILT from a bare domain (Google answers
any domain; an unknown one returns no articles), and a topic id from a mid
plus the edition (used for Headlines, /m/05jhg).
"""
import base64
import binascii

HEADLINES_MID = "/m/05jhg"


def b64decode(value):
    value = (value or "").strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(value + "=" * (-len(value) % 4))


def b64encode(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_varint(raw, i):
    shift = value = 0
    while True:
        if i >= len(raw):
            raise ValueError("truncated varint")
        byte = raw[i]
        i += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, i


def encode(fields):
    """[(field, int | str | bytes | [nested fields])] -> protobuf bytes."""
    out = bytearray()
    for field, value in fields:
        if isinstance(value, int):
            out += _varint(field << 3) + _varint(value)
            continue
        if isinstance(value, list):
            value = encode(value)
        if isinstance(value, str):
            value = value.encode()
        out += _varint(field << 3 | 2) + _varint(len(value)) + value
    return bytes(out)


def decode(raw):
    """protobuf bytes -> {field: [values]} (length-delimited values stay
    bytes; nested messages are decoded on demand with decode())."""
    out, i = {}, 0
    while i < len(raw):
        key, i = _read_varint(raw, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _read_varint(raw, i)
        elif wire == 2:
            length, i = _read_varint(raw, i)
            value = bytes(raw[i:i + length])
            if len(value) != length:
                raise ValueError("truncated field")
            i += length
        elif wire == 5:
            value, i = bytes(raw[i:i + 4]), i + 4
        elif wire == 1:
            value, i = bytes(raw[i:i + 8]), i + 8
        else:
            raise ValueError(f"unsupported wire type {wire}")
        out.setdefault(field, []).append(value)
    return out


def _first(msg, field):
    values = msg.get(field) or []
    return values[0] if values else None


def _wrap(inner_fields):
    inner = b64encode(encode(inner_fields))
    return b64encode(encode([(1, 0), (5, [(1, 10), (4, inner), (10, 1)])]))


def topic_id(mid, language, country=None):
    """A Knowledge Graph topic in one edition (the nav menu omits the
    country for some topics; Google accepts both)."""
    body = [(1, mid), (2, language)]
    if country:
        body.append((3, country))
    return _wrap([(1, 16), (2, body), (5, 0)])


def headlines_id(edition):
    return topic_id(HEADLINES_MID, edition.language, edition.country)


def publication_id(domain):
    return _wrap([(1, 18), (2, [(1, 12), (13, [(1, domain)])]), (5, 0)])


def _inner(value):
    """A CAAq… id -> its decoded inner message, or None."""
    try:
        outer = decode(b64decode(value))
        body = _first(outer, 5)
        if not isinstance(body, bytes):
            return None
        inner_b64 = _first(decode(body), 4)
        if not isinstance(inner_b64, bytes):
            return None
        return decode(b64decode(inner_b64.decode()))
    except (ValueError, binascii.Error, UnicodeDecodeError, TypeError):
        return None


def describe(value):
    """Classify an id: {"kind": "topic" | "publication" | "story" | "local"
    | "section" | "article" | None, …details}."""
    value = (value or "").strip()
    if value.startswith(("CBMi", "CAIi")):
        return {"kind": "article"}
    if value.startswith("CAQ"):
        return {"kind": "section"}
    if not value.startswith("CAAq"):
        return {"kind": None}
    inner = _inner(value)
    if inner is None:
        return {"kind": None}
    kind = _first(inner, 1)
    try:
        body = decode(_first(inner, 2) or b"")
    except ValueError:
        return {"kind": None}
    if kind == 16:
        mid = _first(body, 1)
        return {"kind": "topic", "mid": mid.decode("utf-8", "replace") if isinstance(mid, bytes) else None}
    if kind == 18:
        marker = _first(body, 7)
        if isinstance(marker, bytes):
            marker = marker.decode("utf-8", "replace")
            if marker.startswith("story"):
                return {"kind": "story"}
            if marker.startswith("local"):
                return {"kind": "local"}
        if _first(body, 1) == 12:
            try:
                domain = _first(decode(_first(body, 13) or b""), 1)
            except ValueError:
                domain = None
            return {"kind": "publication",
                    "domain": domain.decode("utf-8", "replace") if isinstance(domain, bytes) else None}
    return {"kind": "topic"}


def publication_domain(value):
    info = describe(value)
    return info.get("domain") if info["kind"] == "publication" else None
