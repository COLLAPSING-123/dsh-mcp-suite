# -*- coding: utf-8 -*-
"""Document readers for the `docs` MCP profile.

Pure standard library: .docx / .pptx / .xlsx are OPC (zip + XML), .md is
plain text, and .pdf falls back to a small built-in extractor when no
PDF library is installed.
"""
from __future__ import annotations

import datetime
import os
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

MAX_BYTES = 80 * 1024 * 1024


class DocError(Exception):
    pass


# --------------------------------------------------------------------- utils
def _check(path):
    if not path:
        raise DocError("path is required")
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        raise DocError("file not found: %s" % path)
    if os.path.isdir(path):
        raise DocError("is a directory: %s" % path)
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise DocError("file too large (%d bytes > %d): %s" % (size, MAX_BYTES, path))
    return path


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _q(tag, uri):
    return "{%s}%s" % (uri, tag)


# ---------------------------------------------------------------------- docx
def docx_to_text(path):
    path = _check(path)
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except KeyError:
        raise DocError("not a valid .docx (missing word/document.xml): %s" % path)
    except zipfile.BadZipFile:
        raise DocError("not a zip container, maybe .doc not .docx: %s" % path)

    root = ET.fromstring(xml)
    body = root.find(_q("body", W_NS))
    if body is None:
        raise DocError("empty document body")

    out = []
    for el in body:
        tag = el.tag.split("}")[-1]
        if tag == "p":
            out.append(_docx_paragraph(el))
        elif tag == "tbl":
            for row in el.findall(_q("tr", W_NS)):
                cells = []
                for cell in row.findall(_q("tc", W_NS)):
                    cells.append(_docx_inline(cell).strip())
                out.append("| " + " | ".join(cells) + " |")
            out.append("")
        elif tag == "sdt":
            out.append(_docx_inline(el))
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _docx_paragraph(el):
    text = _docx_inline(el)
    level = 0
    ppr = el.find(_q("pPr", W_NS))
    if ppr is not None:
        style = ppr.find(_q("pStyle", W_NS))
        if style is not None:
            val = (style.get(_q("val", W_NS)) or "").lower()
            m = re.match(r"heading(\d)", val)
            if m:
                level = int(m.group(1))
            elif val == "title":
                level = 1
    if level and text.strip():
        return "#" * min(level, 6) + " " + text.strip()
    return text


def _docx_inline(el):
    parts = []
    for node in el.iter():
        tag = node.tag.split("}")[-1]
        if tag == "t":
            parts.append(node.text or "")
        elif tag == "tab":
            parts.append("\t")
        elif tag in ("br", "cr"):
            parts.append("\n")
    return "".join(parts)


# ---------------------------------------------------------------------- pptx
def pptx_to_text(path):
    path = _check(path)
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise DocError("not a zip container, maybe .ppt not .pptx: %s" % path)
    with zf:
        names = [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        if not names:
            raise DocError("no slides found in %s" % path)
        names.sort(key=lambda n: int(re.search(r"slide(\d+)\.xml", n).group(1)))
        chunks = []
        for idx, name in enumerate(names, 1):
            root = ET.fromstring(zf.read(name))
            lines = []
            for para in root.iter(_q("p", A_NS)):
                text = "".join(t.text or "" for t in para.iter(_q("t", A_NS)))
                if text.strip():
                    lines.append(text.strip())
            note = ""
            notes_name = name.replace("slides/slide", "notesSlides/notesSlide")
            if notes_name in zf.namelist():
                try:
                    nroot = ET.fromstring(zf.read(notes_name))
                    ntext = "".join(t.text or "" for t in nroot.iter(_q("t", A_NS))).strip()
                    if ntext:
                        note = ntext
                except Exception:
                    note = ""
            block = "## Slide %d\n%s" % (idx, "\n".join(lines) if lines else "(no text)")
            if note:
                block += "\n\n> 备注：%s" % note
            chunks.append(block)
        return "\n\n".join(chunks)


# ---------------------------------------------------------------------- xlsx
def xlsx_to_text(path, max_rows=200):
    path = _check(path)
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise DocError("not a zip container, maybe .xls not .xlsx: %s" % path)
    with zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sroot.findall(_q("si", S_NS)):
                shared.append("".join(t.text or "" for t in si.iter(_q("t", S_NS))))
        sheets = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not sheets:
            raise DocError("no worksheets in %s" % path)
        out = []
        for name in sheets:
            root = ET.fromstring(zf.read(name))
            out.append("## %s" % name.split("/")[-1].replace(".xml", ""))
            count = 0
            for row in root.iter(_q("row", S_NS)):
                if count >= max_rows:
                    out.append("... (truncated at %d rows)" % max_rows)
                    break
                cells = []
                for c in row.findall(_q("c", S_NS)):
                    v = c.find(_q("v", S_NS))
                    if v is None or v.text is None:
                        cells.append("")
                        continue
                    if c.get("t") == "s":
                        try:
                            cells.append(shared[int(v.text)])
                        except (ValueError, IndexError):
                            cells.append(v.text)
                    else:
                        cells.append(v.text)
                out.append("| " + " | ".join(cells) + " |")
                count += 1
            out.append("")
        return "\n".join(out).strip()


# ----------------------------------------------------------------------- pdf
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_TEXT_OP = re.compile(rb"\((?:\\.|[^\\()])*\)\s*Tj|\[(?:[^\[\]]|\\.)*\]\s*TJ|T\*|ET|BT")


def pdf_to_text(path, max_chars=200_000):
    path = _check(path)
    with open(path, "rb") as fh:
        raw = fh.read()

    try:  # prefer a real library when one happens to be installed
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            pages.append("## Page %d\n%s" % (i, (page.extract_text() or "").strip()))
        text = "\n\n".join(pages)
        if text.strip():
            return text[:max_chars]
    except Exception:
        pass

    chunks = []
    for blob in _STREAM.findall(raw):
        try:
            data = zlib.decompress(blob)
        except zlib.error:
            data = blob
        text = _pdf_content_to_text(data)
        if text.strip():
            chunks.append(text)

    result = "\n".join(chunks).strip()
    if not result:
        raise DocError(
            "no extractable text layer in %s (scanned/image-only PDF or CID-encoded "
            "fonts). Needs OCR or a dedicated extractor." % path
        )
    return result[:max_chars]


def _pdf_content_to_text(data):
    out = []
    for match in _TEXT_OP.finditer(data):
        token = match.group(0)
        if token in (b"T*", b"ET"):
            out.append("\n")
            continue
        if token == b"BT":
            continue
        for literal in re.finditer(rb"\((?:\\.|[^\\()])*\)", token):
            out.append(_pdf_unescape(literal.group(0)[1:-1]))
        for hexstr in re.finditer(rb"<([0-9A-Fa-f\s]+)>", token):
            out.append(_pdf_hex_to_text(hexstr.group(1)))
        out.append(" ")
    return "".join(out)


def _pdf_unescape(raw):
    out = bytearray()
    i, n = 0, len(raw)
    mapping = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
    while i < n:
        ch = raw[i : i + 1]
        if ch == b"\\" and i + 1 < n:
            nxt = raw[i + 1 : i + 2]
            if nxt in mapping:
                out += mapping[nxt]
                i += 2
                continue
            if nxt in (b"(", b")", b"\\"):
                out += nxt
                i += 2
                continue
            m = re.match(rb"[0-7]{1,3}", raw[i + 1 : i + 4])
            if m:
                out.append(int(m.group(0), 8) & 0xFF)
                i += 1 + len(m.group(0))
                continue
            out += nxt
            i += 2
            continue
        out += ch
        i += 1
    return out.decode("latin-1", "replace")


def _pdf_hex_to_text(hexbytes):
    cleaned = re.sub(rb"\s+", b"", hexbytes)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        raw = bytes.fromhex(cleaned.decode("ascii"))
    except Exception:
        return ""
    if raw[:2] == b"\xfe\xff":
        try:
            return raw.decode("utf-16-be", "replace")
        except Exception:
            return ""
    return raw.decode("latin-1", "replace")


# ------------------------------------------------------------------------ md
def read_markdown(path, max_chars=200_000):
    return _read_text(_check(path))[:max_chars]


def markdown_outline(path):
    text = _read_text(_check(path))
    lines = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lines.append("%s %s" % ("  " * (len(m.group(1)) - 1) + "-", m.group(2).strip()))
    return "\n".join(lines) if lines else "(no headings found)"


# -------------------------------------------------------------------- router
HANDLERS = {
    ".docx": ("word", docx_to_text),
    ".pptx": ("powerpoint", pptx_to_text),
    ".xlsx": ("excel", xlsx_to_text),
    ".xlsm": ("excel", xlsx_to_text),
    ".pdf": ("pdf", pdf_to_text),
    ".md": ("markdown", read_markdown),
    ".markdown": ("markdown", read_markdown),
    ".txt": ("text", read_markdown),
    ".csv": ("text", read_markdown),
    ".json": ("text", read_markdown),
    ".log": ("text", read_markdown),
}

LEGACY = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}
SUPPORTED = sorted(HANDLERS) + sorted(LEGACY)


def read_any(path, max_chars=200_000):
    path = _check(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in LEGACY:
        raise DocError(
            "%s is the legacy binary format; open it in Office and re-save as %s, "
            "then read that." % (ext, LEGACY[ext])
        )
    if ext not in HANDLERS:
        raise DocError(
            "unsupported extension %r; supported: %s" % (ext, ", ".join(SUPPORTED))
        )
    kind, fn = HANDLERS[ext]
    text = fn(path)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated at %d chars ...]" % max_chars
    return kind, text


def describe(path):
    path = _check(path)
    ext = os.path.splitext(path)[1].lower()
    stat = os.stat(path)
    kind = HANDLERS[ext][0] if ext in HANDLERS else ("legacy/unknown" if ext in LEGACY else "unknown")
    return {
        "path": path,
        "extension": ext,
        "kind": kind,
        "size_bytes": stat.st_size,
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "supported": ext in HANDLERS,
    }
