"""Turn equation notation into characters Word and the preview can show."""

from __future__ import annotations

import re

_SUPER = {
    "0": "\u2070",
    "1": "\u00b9",
    "2": "\u00b2",
    "3": "\u00b3",
    "4": "\u2074",
    "5": "\u2075",
    "6": "\u2076",
    "7": "\u2077",
    "8": "\u2078",
    "9": "\u2079",
    "+": "\u207a",
    "-": "\u207b",
    "=": "\u207c",
    "(": "\u207d",
    ")": "\u207e",
    "n": "\u207f",
    "i": "\u2071",
    "a": "\u1d43",
    "b": "\u1d47",
    "c": "\u1d9c",
    "d": "\u1d48",
    "e": "\u1d49",
    "h": "\u02b0",
    "k": "\u1d4f",
    "m": "\u1d50",
    "o": "\u1d52",
    "p": "\u1d56",
    "t": "\u1d57",
    "u": "\u1d58",
    "v": "\u1d5b",
    "x": "\u02e3",
}
_SUB = {
    "0": "\u2080",
    "1": "\u2081",
    "2": "\u2082",
    "3": "\u2083",
    "4": "\u2084",
    "5": "\u2085",
    "6": "\u2086",
    "7": "\u2087",
    "8": "\u2088",
    "9": "\u2089",
    "+": "\u208a",
    "-": "\u208b",
    "=": "\u208c",
    "(": "\u208d",
    ")": "\u208e",
    "a": "\u2090",
    "e": "\u2091",
    "h": "\u2095",
    "i": "\u1d62",
    "k": "\u2096",
    "l": "\u2097",
    "m": "\u2098",
    "n": "\u2099",
    "o": "\u2092",
    "p": "\u209a",
    "s": "\u209b",
    "t": "\u209c",
    "x": "\u2093",
}
_COMMANDS = {
    "alpha": "\u03b1",
    "beta": "\u03b2",
    "gamma": "\u03b3",
    "delta": "\u03b4",
    "Delta": "\u0394",
    "epsilon": "\u03b5",
    "theta": "\u03b8",
    "lambda": "\u03bb",
    "mu": "\u03bc",
    "pi": "\u03c0",
    "sigma": "\u03c3",
    "Sigma": "\u03a3",
    "phi": "\u03c6",
    "omega": "\u03c9",
    "Omega": "\u03a9",
    "leq": "\u2264",
    "le": "\u2264",
    "geq": "\u2265",
    "ge": "\u2265",
    "neq": "\u2260",
    "ne": "\u2260",
    "times": "\u00d7",
    "pm": "\u00b1",
    "infty": "\u221e",
    "sum": "\u2211",
    "int": "\u222b",
    "sqrt": "\u221a",
    "cdot": "\u00b7",
    "div": "\u00f7",
    "approx": "\u2248",
    "rightarrow": "\u2192",
    "to": "\u2192",
    "degree": "\u00b0",
    "partial": "\u2202",
}
_FRAC = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_CMD = re.compile(r"\\([A-Za-z]+)")
_GROUP_SUPER = re.compile(r"\^\{([^{}]*)\}")
_GROUP_SUB = re.compile(r"_\{([^{}]*)\}")
_CHAR_SUPER = re.compile(r"\^([A-Za-z0-9])")
_CHAR_SUB = re.compile(r"_(\d+|[A-Za-z](?![A-Za-z]))")
_FROM_SUPER = {symbol: base for base, symbol in _SUPER.items()}
_FROM_SUB = {symbol: base for base, symbol in _SUB.items()}
_MATH_SYMBOLS = set(_COMMANDS.values()) | {"\u2044", "\u221a"}


def normalize_math(text: str) -> str:
    if not text or not any(mark in text for mark in "\\^_"):
        return text
    return _normalize(text)


def split_runs(text: str) -> list[tuple[str, str]]:
    """Group text into plain, superscript, subscript, and math-symbol runs.

    Superscript and subscript runs use the base characters. The caller marks
    them with Word's vertical alignment.
    """
    if not text:
        return []
    runs: list[tuple[str, str]] = []
    kind = _class(text[0])
    chars = [_base(text[0], kind)]
    for char in text[1:]:
        nxt = _class(char)
        if nxt == kind:
            chars.append(_base(char, nxt))
            continue
        runs.append((kind, "".join(chars)))
        kind = nxt
        chars = [_base(char, nxt)]
    runs.append((kind, "".join(chars)))
    return [(item_kind, item) for item_kind, item in runs if item]


def _normalize(text: str) -> str:
    text = _FRAC.sub(lambda match: _fraction(match.group(1), match.group(2)), text)
    text = _SQRT.sub(lambda match: "\u221a" + _normalize(match.group(1)), text)
    text = _CMD.sub(lambda match: _COMMANDS.get(match.group(1), match.group(0)), text)
    text = _GROUP_SUPER.sub(lambda match: _script(_normalize(match.group(1)), superscript=True), text)
    text = _GROUP_SUB.sub(lambda match: _script(_normalize(match.group(1)), superscript=False), text)
    text = _CHAR_SUPER.sub(lambda match: _script(match.group(1), superscript=True), text)
    text = _CHAR_SUB.sub(lambda match: _script(match.group(1), superscript=False), text)
    return text


def _fraction(numerator: str, denominator: str) -> str:
    return (
        _script(_normalize(numerator), superscript=True)
        + "\u2044"
        + _script(_normalize(denominator), superscript=False)
    )


def _script(text: str, *, superscript: bool) -> str:
    table = _SUPER if superscript else _SUB
    return "".join(table.get(char, char) for char in text)


def _class(char: str) -> str:
    if char in _FROM_SUPER:
        return "super"
    if char in _FROM_SUB:
        return "sub"
    if char in _MATH_SYMBOLS:
        return "math"
    return "plain"


def _base(char: str, kind: str) -> str:
    if kind == "super":
        return _FROM_SUPER.get(char, char)
    if kind == "sub":
        return _FROM_SUB.get(char, char)
    return char
