import re

VANITY_MAP = {
    "1": ".@/",
    "2": "ABC",
    "3": "DEF",
    "4": "GHI",
    "5": "JKL",
    "6": "MNO",
    "7": "PQRS",
    "8": "TUV",
    "9": "WXYZ",
    "0": "_*",
}

REGEX_MAP = {
    "1": "/",
    "2": "[ABC]",
    "3": "[DEF]",
    "4": "[GHI]",
    "5": "[JKL]",
    "6": "[MNO]",
    "7": "[PQRS]",
    "8": "[TUV]",
    "9": "[WXYZ]",
    "0": ".",
}

MODES = [
    "strict",
    "linear",
    "fuzzy",
]


def to_regex(numbers: str, mode: str = "linear") -> re.Pattern:
    if mode == "linear":
        return to_regex_linear(numbers, False)
    elif mode == "strict":
        return to_regex_linear(numbers, True)
    elif mode == "fuzzy":
        return to_regex_fuzzy(numbers)
    else:
        raise RuntimeError(f"unknown mode {mode}, expect one of linear, strict, fuzzy")


def to_regex_linear(numbers: str, strict: bool = False) -> re.Pattern:
    """Convert a string of numbers into a fuzzy vanity regular expression pattern."""
    regex = ""
    prev = None
    has_slash = False
    for char in numbers:
        if char not in REGEX_MAP:
            continue
        if char == "1":
            has_slash = True
        if char == "0" and prev == "0":
            # Double 0 translates to .*
            regex += "*"
        else:
            regex += REGEX_MAP[char]
        prev = char

    # If no slash has been specified, assume we're searching for artist.
    if not has_slash:
        regex += ".*/"

    # If a slash is at the beginning, then we don't need ^ in strict mode.
    if strict and regex[0] != "/":
        regex = "^" + regex

    return re.compile(regex, re.IGNORECASE)


def to_regex_fuzzy(numbers: str) -> re.Pattern:
    regex = ""
    has_slash = False
    for char in numbers:
        if char not in REGEX_MAP:
            continue
        if char == "1":
            has_slash = True
        regex += REGEX_MAP[char] + ".*"
    if not has_slash:
        regex += "/"
    return re.compile(regex, re.IGNORECASE)
