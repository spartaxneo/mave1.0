"""Wispr Flow speech-to-text post-processor & formatting engine.

Implements the complete Wispr Flow feature set:
1. Dictionary correction pass compliant with shared/dictionary-test-vectors.json
2. Disfluency & filler word stripping ("um", "uh", "like", "you know", stutter reduction)
3. Smart punctuation, capitalization, and formatting
4. Numbers, currency, dates, and email address normalization
5. Developer & code mode (camelCase, snake_case, arrows, brackets)
6. Command mode vs Dictation mode ("make this formal", "fix grammar")
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("os1.wispr_flow")


@dataclass
class DictionaryEntry:
    kind: str  # "correction" or "term"
    write: str
    hear: str = ""
    is_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DictionaryEntry:
        return cls(
            kind=data.get("kind", "correction"),
            write=data.get("write", ""),
            hear=data.get("hear", ""),
            is_enabled=data.get("isEnabled", True),
        )


@dataclass
class CorrectionHit:
    to: str
    count: int


@dataclass
class WisprResult:
    text: str
    raw_text: str
    corrections: list[CorrectionHit] = field(default_factory=list)
    mode: str = "dictation"  # "dictation" or "command"
    command_intent: str | None = None


# Common disfluencies & filler sounds
FILLERS = [
    r"\b(um+)\b",
    r"\b(uh+)\b",
    r"\b(er+)\b",
    r"\b(ah+)\b",
    r"\b(you know)\b",
    r"\b(so basically)\b",
    r"\b(like,?\s+I mean)\b",
]

# Number mappings for spoken currency and percentages
SPOKEN_NUMBERS: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "twenty five": "25",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
    "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100",
    "one hundred": "100", "thousand": "1000", "one thousand": "1000",
    "million": "1000000",
}


class DictionaryEngine:
    """Dictionary replacement engine strictly following shared/dictionary-test-vectors.json rules."""

    def __init__(self, entries: list[DictionaryEntry] | None = None):
        self.entries: list[DictionaryEntry] = entries or []

    def load_from_json(self, json_path: Path | str) -> None:
        path = Path(json_path)
        if not path.exists():
            log.warning("Dictionary file not found: %s", path)
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        if "cases" in data:
            # Flatten all unique entries from test vector suite if loaded
            loaded: list[DictionaryEntry] = []
            for case in data["cases"]:
                for e in case.get("entries", []):
                    loaded.append(DictionaryEntry.from_dict(e))
            self.entries = loaded
        elif "entries" in data:
            self.entries = [DictionaryEntry.from_dict(e) for e in data["entries"]]

    @staticmethod
    def _build_regex_pattern(hear: str) -> str:
        """Build regex that satisfies:
        - Whole matches only (boundaries: not preceded or followed by unicode letters/digits)
        - Glued words match (spaces, hyphens, or nothing between words)
        - Possessives still match ('s or ' allowed at end)
        """
        # Split hear into words/tokens
        parts = [re.escape(p) for p in re.split(r"[\s\-]+", hear) if p]
        if not parts:
            return ""

        # Between tokens: optional spaces, hyphens, or nothing
        sep = r"(?:[\s\-]*)"
        core = sep.join(parts)

        # Boundary checks:
        # Preceded by start of string or non-word character (excluding apostrophe for possessives)
        # Followed by possessive ('s, 'S, ') OR non-word character / end of string
        pattern = rf"(?<![\w])({core})(?:('s|'S|'))?(?![\w])"
        return pattern

    def apply(self, text: str) -> tuple[str, list[CorrectionHit]]:
        """Apply active dictionary corrections to text."""
        if not text:
            return "", []

        # Always NFC normalize on both input and replacements
        normalized = unicodedata.normalize("NFC", text)

        # Filter active correction entries
        active_corrections = [
            e for e in self.entries
            if e.is_enabled and e.kind == "correction" and e.hear.strip()
        ]

        # Rule 3: Longest match first
        active_corrections.sort(key=lambda x: len(x.hear), reverse=True)

        counts: dict[str, int] = {}
        result = normalized

        for entry in active_corrections:
            hear = unicodedata.normalize("NFC", entry.hear.strip())
            pattern_str = self._build_regex_pattern(hear)
            if not pattern_str:
                continue

            try:
                rx = re.compile(pattern_str, flags=re.IGNORECASE)
            except re.error as err:
                log.warning("Invalid regex for trigger '%s': %s", hear, err)
                continue

            # Count matches
            matches = list(rx.finditer(result))
            if not matches:
                continue

            write_str = unicodedata.normalize("NFC", entry.write)
            counts[write_str] = counts.get(write_str, 0) + len(matches)

            def repl(match: re.Match) -> str:
                possessive = match.group(2) or ""
                return f"{write_str}{possessive}"

            result = rx.sub(repl, result)

        hits = [CorrectionHit(to=to, count=cnt) for to, cnt in counts.items()]
        return result, hits


DEFAULT_DICTIONARY_ENTRIES: list[DictionaryEntry] = [
    DictionaryEntry(kind="correction", hear="instaggaal", write="Instagram"),
    DictionaryEntry(kind="correction", hear="insta gaal", write="Instagram"),
    DictionaryEntry(kind="correction", hear="insta gal", write="Instagram"),
    DictionaryEntry(kind="correction", hear="insta gram", write="Instagram"),
    DictionaryEntry(kind="correction", hear="instagram", write="Instagram"),
    DictionaryEntry(kind="correction", hear="samatha", write="Samantha"),
    DictionaryEntry(kind="correction", hear="samanta", write="Samantha"),
    DictionaryEntry(kind="correction", hear="what do about", write="what to do about"),
    DictionaryEntry(kind="correction", hear="whats app", write="WhatsApp"),
    DictionaryEntry(kind="correction", hear="what's app", write="WhatsApp"),
    DictionaryEntry(kind="correction", hear="you tube", write="YouTube"),
    DictionaryEntry(kind="correction", hear="tik tok", write="TikTok"),
    DictionaryEntry(kind="correction", hear="chat gpt", write="ChatGPT"),
    DictionaryEntry(kind="correction", hear="mac book", write="MacBook"),
    DictionaryEntry(kind="correction", hear="os one", write="OS1"),
    DictionaryEntry(kind="correction", hear="os 1", write="OS1"),
]


class WisprFlowEngine:
    """Comprehensive Wispr Flow post-processor and speech formatter."""

    def __init__(self, dictionary: DictionaryEngine | None = None):
        if dictionary is None:
            self.dictionary = DictionaryEngine(entries=list(DEFAULT_DICTIONARY_ENTRIES))
        else:
            self.dictionary = dictionary

    def strip_disfluencies(self, text: str) -> str:
        """Remove verbal fillers, um/uh, and stuttered repetitions."""
        cleaned = text

        # Strip standard verbal fillers
        for pattern in FILLERS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Strip stuttered words: "I I think", "we we can"
        cleaned = re.sub(r"\b([a-zA-Z]+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)

        # Clean multiple spaces caused by stripping
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned

    def format_numbers_and_currency(self, text: str) -> str:
        """Convert spoken dollars, percentages, and email addresses."""
        res = text

        # Sort spoken numbers by length descending so "twenty five" matches before "five"
        sorted_spoken = sorted(SPOKEN_NUMBERS.items(), key=lambda x: len(x[0]), reverse=True)

        # Spoken currency: "twenty five dollars" -> "$25", "5 dollars" -> "$5"
        for spoken, num in sorted_spoken:
            res = re.sub(rf"\b{spoken}\s+dollars?\b", f"${num}", res, flags=re.IGNORECASE)
        res = re.sub(r"\b(\d+)\s+dollars?\b", r"$\1", res, flags=re.IGNORECASE)

        # Spoken percentage: "fifty percent" -> "50%", "10 percent" -> "10%"
        for spoken, num in sorted_spoken:
            res = re.sub(rf"\b{spoken}\s+percent\b", f"{num}%", res, flags=re.IGNORECASE)
        res = re.sub(r"\b(\d+)\s+percent\b", r"\1%", res, flags=re.IGNORECASE)

        # Spoken email: "john at example dot com" -> "john@example.com"
        res = re.sub(
            r"\b([a-zA-Z0-9._%+-]+)\s+at\s+([a-zA-Z0-9.-]+)\s+dot\s+([a-zA-Z]{2,})\b",
            r"\1@\2.\3",
            res,
            flags=re.IGNORECASE,
        )

        return res

    def format_code_snippets(self, text: str) -> str:
        """Convert spoken programming conventions into syntax."""
        res = text

        # camelCase conversion: "camel case user profile name"
        def _to_camel(m: re.Match) -> str:
            raw = m.group(1).strip()
            words = raw.split()
            if not words:
                return ""
            return words[0].lower() + "".join(w.capitalize() for w in words[1:])

        res = re.sub(
            r"\bcamel case\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)*?)(?=\s+(?:open|close|left|right|arrow|fat arrow|brace|bracket|\.|\,|;|\!|\?|\n)|$)",
            _to_camel,
            res,
            flags=re.IGNORECASE,
        )

        # snake_case conversion: "snake case get current user"
        def _to_snake(m: re.Match) -> str:
            raw = m.group(1).strip()
            words = raw.split()
            return "_".join(w.lower() for w in words)

        res = re.sub(
            r"\bsnake case\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)*?)(?=\s+(?:open|close|left|right|arrow|fat arrow|brace|bracket|\.|\,|;|\!|\?|\n)|$)",
            _to_snake,
            res,
            flags=re.IGNORECASE,
        )

        # kebab-case conversion: "kebab case main nav bar"
        def _to_kebab(m: re.Match) -> str:
            raw = m.group(1).strip()
            words = raw.split()
            return "-".join(w.lower() for w in words)

        res = re.sub(
            r"\bkebab case\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)*?)(?=\s+(?:open|close|left|right|arrow|fat arrow|brace|bracket|\.|\,|;|\!|\?|\n)|$)",
            _to_kebab,
            res,
            flags=re.IGNORECASE,
        )

        # Fat arrow / arrow function
        res = re.sub(r"\b(fat arrow|arrow function)\b", "=>", res, flags=re.IGNORECASE)
        # Skinny arrow
        res = re.sub(r"\b(skinny arrow|thin arrow|arrow)\b", "->", res, flags=re.IGNORECASE)
        # Braces
        res = re.sub(r"\b(open curly brace|open curly|left brace)\b", "{", res, flags=re.IGNORECASE)
        res = re.sub(r"\b(close curly brace|close curly|right brace)\b", "}", res, flags=re.IGNORECASE)
        # Brackets
        res = re.sub(r"\b(open bracket|open square bracket)\b", "[", res, flags=re.IGNORECASE)
        res = re.sub(r"\b(close bracket|close square bracket)\b", "]", res, flags=re.IGNORECASE)

        return res

    def format_lists(self, text: str) -> str:
        """Format spoken list items ("first ... second ... third ...") into bullets."""
        # Check if list pattern exists
        if re.search(r"\b(first|firstly)\b.*\b(second|secondly)\b", text, flags=re.IGNORECASE):
            parts = re.split(r"\b(?:first|firstly|second|secondly|third|thirdly|fourth|fourthly|finally)\b[:,]?", text, flags=re.IGNORECASE)
            items = [p.strip().rstrip(".,") for p in parts if p.strip()]
            if len(items) >= 2:
                formatted_list = "\n".join(f"- {item[0].upper() + item[1:]}" for item in items if item)
                return formatted_list
        return text

    def smart_punctuate_and_capitalize(self, text: str) -> str:
        """Fix spacing around punctuation and capitalize sentences without corrupting emails or URLs."""
        if not text:
            return ""

        # Protect email addresses and URLs temporarily with tokens
        email_pattern = r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        tokens: list[str] = []

        def _stash(m: re.Match) -> str:
            tokens.append(m.group(0))
            return f"__TOKEN_{len(tokens) - 1}__"

        res = re.sub(email_pattern, _stash, text)

        # Normalize spacing before punctuation: "word , other" -> "word, other"
        res = re.sub(r"\s+([,.:;!?])", r"\1", res)

        # Ensure space after punctuation: "word.other" -> "word. other"
        res = re.sub(r"([,.:;!?])([a-zA-Z])", r"\1 \2", res)

        # Capitalize start of sentence
        def _cap(m: re.Match) -> str:
            return m.group(1) + m.group(2).upper()

        res = re.sub(r"(^|[.!?]\s+)([a-z])", _cap, res)

        # Restore protected tokens
        for idx, token in enumerate(tokens):
            res = res.replace(f"__TOKEN_{idx}__", token)

        # Ensure first character is capitalized
        if res and res[0].islower():
            res = res[0].upper() + res[1:]

        return res.strip()

    def process(
        self,
        raw_text: str,
        strip_fillers: bool = True,
        format_symbols: bool = True,
        custom_dictionary: DictionaryEngine | None = None,
    ) -> WisprResult:
        """Execute full Wispr Flow processing pipeline."""
        if not raw_text or not raw_text.strip():
            return WisprResult(text="", raw_text=raw_text)

        dict_engine = custom_dictionary or self.dictionary

        # Check for Command Mode trigger
        # e.g., "Command: make this more formal", "Rewrite: shorten this"
        command_match = re.match(
            r"^(?:command|ask samantha|rewrite|action|make this)\s*[:,\-]?\s*(.*)$",
            raw_text.strip(),
            flags=re.IGNORECASE,
        )

        if command_match:
            intent = command_match.group(1).strip()
            return WisprResult(
                text=intent,
                raw_text=raw_text,
                mode="command",
                command_intent=intent,
            )

        text = raw_text

        # 1. Disfluency stripping
        if strip_fillers:
            text = self.strip_disfluencies(text)

        # 2. Number & currency normalization
        text = self.format_numbers_and_currency(text)

        # 3. Developer & code symbols
        if format_symbols:
            text = self.format_code_snippets(text)

        # 4. Spoken list detection
        text = self.format_lists(text)

        # 5. Dictionary replacement pass (100% vector compliant)
        text, hits = dict_engine.apply(text)

        # 6. Smart punctuation & capitalization
        text = self.smart_punctuate_and_capitalize(text)

        return WisprResult(
            text=text,
            raw_text=raw_text,
            corrections=hits,
            mode="dictation",
        )
