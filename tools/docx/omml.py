"""Office Math for formulas that character runs cannot stack."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from tools.docx.math import command_symbol

_FORMULA = re.compile(r"\\frac|\\sqrt|_\{|\^\{")
_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def is_office_formula(text: str) -> bool:
    return bool(_FORMULA.search(text or ""))


def omml_xml(notation: str) -> str:
    body = _sequence(notation or "")
    return f'<m:oMath xmlns:m="{_NS}">{body}</m:oMath>'


def _run(text: str) -> str:
    if not text:
        return ""
    return f'<m:r><m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def _sequence(text: str) -> str:
    parts: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index].isspace():
            parts.append(_run(" "))
            index += 1
            continue
        atom, index = _atom(text, index)
        sub = ""
        sup = ""
        seen: set[str] = set()
        while index < length and text[index] in "_^" and text[index] not in seen:
            kind = text[index]
            seen.add(kind)
            body, index = _script(text, index + 1)
            if kind == "_":
                sub = body
            else:
                sup = body
        parts.append(_scripted(atom, sub, sup) if sub or sup else atom)
    return "".join(part for part in parts if part) or _run("")


def _scripted(base: str, sub: str, sup: str) -> str:
    if sub and sup:
        return f"<m:sSubSup><m:e>{base}</m:e><m:sub>{sub}</m:sub><m:sup>{sup}</m:sup></m:sSubSup>"
    if sub:
        return f"<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>"
    return f"<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>"


def _atom(text: str, index: int) -> tuple[str, int]:
    if text.startswith("\\frac", index) and _brace_ahead(text, index + 5):
        numerator, index = _group_after(text, index + 5)
        denominator, index = _group_after(text, index)
        return f"<m:f><m:num>{_sequence(numerator)}</m:num><m:den>{_sequence(denominator)}</m:den></m:f>", index
    if text.startswith("\\sqrt", index) and _brace_ahead(text, index + 5):
        body, index = _group_after(text, index + 5)
        rad = (
            "<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr>"
            f"<m:deg/><m:e>{_sequence(body)}</m:e></m:rad>"
        )
        return rad, index
    if text[index] == "\\":
        symbol, index = _command(text, index)
        return _run(symbol), index
    end = index + 1
    while end < len(text) and text[end] not in "\\_^{}":
        end += 1
    return _run(text[index:end]), end


def _script(text: str, index: int) -> tuple[str, int]:
    if index >= len(text):
        return "", index
    if text[index] == "{":
        inner, index = _group(text, index)
        return _sequence(inner), index
    if text[index] == "\\":
        symbol, index = _command(text, index)
        return _run(symbol), index
    return _run(text[index]), index + 1


def _group(text: str, index: int) -> tuple[str, int]:
    depth = 0
    for cursor in range(index, len(text)):
        if text[cursor] == "{":
            depth += 1
        elif text[cursor] == "}":
            depth -= 1
            if depth == 0:
                return text[index + 1 : cursor], cursor + 1
    return text[index + 1 :], len(text)


def _group_after(text: str, index: int) -> tuple[str, int]:
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "{":
        return "", index
    return _group(text, index)


def _brace_ahead(text: str, index: int) -> bool:
    while index < len(text) and text[index].isspace():
        index += 1
    return index < len(text) and text[index] == "{"


def _command(text: str, index: int) -> tuple[str, int]:
    end = index + 1
    while end < len(text) and text[end].isalpha():
        end += 1
    name = text[index + 1 : end]
    if not name:
        return "\\", index + 1
    return command_symbol(name), end
