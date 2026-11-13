"""Turn equation notation into characters Word and the preview can show."""

from __future__ import annotations

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
    "Gamma": "\u0393",
    "delta": "\u03b4",
    "Delta": "\u0394",
    "epsilon": "\u03b5",
    "varepsilon": "\u03b5",
    "zeta": "\u03b6",
    "eta": "\u03b7",
    "theta": "\u03b8",
    "Theta": "\u0398",
    "vartheta": "\u03d1",
    "iota": "\u03b9",
    "kappa": "\u03ba",
    "lambda": "\u03bb",
    "Lambda": "\u039b",
    "mu": "\u03bc",
    "nu": "\u03bd",
    "xi": "\u03be",
    "Xi": "\u039e",
    "pi": "\u03c0",
    "Pi": "\u03a0",
    "varpi": "\u03d6",
    "rho": "\u03c1",
    "varrho": "\u03f1",
    "sigma": "\u03c3",
    "Sigma": "\u03a3",
    "varsigma": "\u03c2",
    "tau": "\u03c4",
    "upsilon": "\u03c5",
    "Upsilon": "\u03a5",
    "phi": "\u03c6",
    "Phi": "\u03a6",
    "varphi": "\u03d5",
    "chi": "\u03c7",
    "psi": "\u03c8",
    "Psi": "\u03a8",
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
    "equiv": "\u2261",
    "rightarrow": "\u2192",
    "to": "\u2192",
    "nabla": "\u2207",
    "partial": "\u2202",
    "degree": "\u00b0",
    "propto": "\u221d",
    "hbar": "\u210f",
}
_FROM_SUPER = {symbol: base for base, symbol in _SUPER.items()}
_FROM_SUB = {symbol: base for base, symbol in _SUB.items()}
_MATH_SYMBOLS = set(_COMMANDS.values()) | {"\u2044", "\u221a"}


def math_runs(text: str) -> list[dict[str, str]]:
    """Split notation into plain text and sub/super runs.

    Digits use Unicode superscripts and subscripts. Greek letters, which have
    no Unicode subscript, keep their characters and set script to sub or super.
    """
    if not text:
        return []
    if not any(mark in text for mark in "\\^_"):
        return [{"text": text}]
    return _parse(text)


def normalize_math(text: str) -> str:
    if not text or not any(mark in text for mark in "\\^_"):
        return text
    return "".join(run["text"] for run in _parse(text))


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


def _parse(text: str) -> list[dict[str, str]]:
    runs: list[dict[str, str]] = []
    plain: list[str] = []

    def flush() -> None:
        if plain:
            runs.append({"text": "".join(plain)})
            plain.clear()

    index = 0
    length = len(text)
    while index < length:
        if text.startswith("\\frac", index) and _brace_ahead(text, index + 5):
            flush()
            numerator, denominator, index = _read_frac(text, index + 5)
            runs.extend(_mark(_parse(numerator), "super"))
            runs.append({"text": "\u2044"})
            runs.extend(_mark(_parse(denominator), "sub"))
            continue
        if text.startswith("\\sqrt", index) and _brace_ahead(text, index + 5):
            flush()
            body, index = _read_group_after(text, index + 5)
            plain.append("\u221a")
            flush()
            runs.extend(_parse(body))
            continue
        if text[index] in "^_" and index + 1 < length:
            flush()
            script = "super" if text[index] == "^" else "sub"
            body, index = _read_script_body(text, index + 1)
            runs.extend(_mark(body, script))
            continue
        if text[index] == "\\":
            symbol, index = _read_command(text, index)
            plain.append(symbol)
            continue
        plain.append(text[index])
        index += 1
    flush()
    return _merge(runs)


def _read_script_body(text: str, index: int) -> tuple[list[dict[str, str]], int]:
    if text[index] == "{":
        end = _matching_brace(text, index)
        return _parse(text[index + 1 : end]), end + 1 if end < len(text) else len(text)
    pieces: list[dict[str, str]] = []
    if text[index] == "\\":
        while index < len(text) and text[index] == "\\" and not _starts_structure(text, index):
            symbol, index = _read_command(text, index)
            pieces.append({"text": symbol})
        return pieces, index
    if text[index].isdigit():
        end = index + 1
        while end < len(text) and text[end].isdigit():
            end += 1
        return [{"text": text[index:end]}], end
    if _is_greek(text[index]):
        while index < len(text) and (_is_greek(text[index]) or text[index] == "\\"):
            if text[index] == "\\":
                if _starts_structure(text, index):
                    break
                symbol, index = _read_command(text, index)
                pieces.append({"text": symbol})
                continue
            pieces.append({"text": text[index]})
            index += 1
        return pieces, index
    return [{"text": text[index]}], index + 1


def _mark(runs: list[dict[str, str]], script: str) -> list[dict[str, str]]:
    table = _SUPER if script == "super" else _SUB
    other = _FROM_SUB if script == "super" else _FROM_SUPER
    marked: list[dict[str, str]] = []
    encoded: list[str] = []
    raw: list[str] = []

    def flush_encoded() -> None:
        if encoded:
            marked.append({"text": "".join(encoded)})
            encoded.clear()

    def flush_raw() -> None:
        if raw:
            marked.append({"text": "".join(raw), "script": script})
            raw.clear()

    for run in runs:
        if run.get("script"):
            flush_encoded()
            flush_raw()
            marked.append(run)
            continue
        for char in run.get("text") or "":
            if char in table:
                flush_raw()
                encoded.append(table[char])
            elif char in other or char.isspace():
                flush_encoded()
                flush_raw()
                marked.append({"text": char})
            else:
                flush_encoded()
                raw.append(char)
    flush_encoded()
    flush_raw()
    return marked


def _merge(runs: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for run in runs:
        text = run.get("text") or ""
        if not text:
            continue
        script = run.get("script")
        if merged and merged[-1].get("script") == script:
            merged[-1]["text"] += text
            continue
        item = {"text": text}
        if script:
            item["script"] = script
        merged.append(item)
    return merged


def _read_command(text: str, index: int) -> tuple[str, int]:
    end = index + 1
    while end < len(text) and text[end].isalpha():
        end += 1
    name = text[index + 1 : end]
    if not name:
        return text[index], index + 1
    return _COMMANDS.get(name, text[index:end]), end


def _read_frac(text: str, index: int) -> tuple[str, str, int]:
    numerator, index = _read_group_after(text, index)
    denominator, index = _read_group_after(text, index)
    return numerator, denominator, index


def _read_group_after(text: str, index: int) -> tuple[str, int]:
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "{":
        return "", index
    end = _matching_brace(text, index)
    return text[index + 1 : end], end + 1 if end < len(text) else len(text)


def _matching_brace(text: str, index: int) -> int:
    depth = 0
    for cursor in range(index, len(text)):
        if text[cursor] == "{":
            depth += 1
        elif text[cursor] == "}":
            depth -= 1
            if depth == 0:
                return cursor
    return len(text)


def _brace_ahead(text: str, index: int) -> bool:
    while index < len(text) and text[index].isspace():
        index += 1
    return index < len(text) and text[index] == "{"


def _starts_structure(text: str, index: int) -> bool:
    return text.startswith("\\frac", index) or text.startswith("\\sqrt", index)


def _is_greek(char: str) -> bool:
    code = ord(char)
    return 0x0370 <= code <= 0x03FF


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
