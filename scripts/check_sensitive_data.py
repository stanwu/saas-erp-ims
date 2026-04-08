#!/usr/bin/env python3
"""Block obvious secrets and likely real PII from being committed."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
]

GENERIC_SECRET_RE = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)\d{3,4}[-.\s]?\d{3,4}(?!\w)"
)
ALLOWLIST_TERMS = {
    "example.com",
    "example.org",
    "example.net",
    ".example",
    "test-secret",
    "test-csrf-secret",
    "dev-secret-key",
    "dev-secret-key-change-in-prod",
    "csrf-secret-change-in-prod",
    "admin12345",
    "demo12345",
    "changeme",
    "your-secret",
}
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".db",
    ".db-wal",
    ".db-shm",
}
ALLOW_COMMENT = "sensitive-data: allow"


def is_probably_phone_false_positive(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) < 8 or len(digits) > 15


def is_allowed_secret(value: str) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in ALLOWLIST_TERMS)


def scan_file(path: Path) -> list[str]:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    issues: list[str] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if ALLOW_COMMENT in line:
            continue

        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(f"{path}:{lineno}: found {label}")

        for match in GENERIC_SECRET_RE.finditer(line):
            value = match.group(1)
            if not is_allowed_secret(value):
                issues.append(f"{path}:{lineno}: found possible hard-coded secret")

        for match in EMAIL_RE.finditer(line):
            domain = match.group(1).lower()
            if not any(term in domain for term in ALLOWLIST_TERMS):
                issues.append(f"{path}:{lineno}: found possible personal email address")

        for match in PHONE_RE.finditer(line):
            candidate = match.group(0)
            if is_probably_phone_false_positive(candidate):
                continue
            if "example" in line.lower():
                continue
            issues.append(f"{path}:{lineno}: found possible phone number")

    return issues


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:] if Path(arg).is_file()]
    issues: list[str] = []
    for path in paths:
        issues.extend(scan_file(path))

    if issues:
        print("Sensitive data scan failed:")
        for issue in issues:
            print(f"  - {issue}")
        print(
            "\nIf a match is intentional test/example data, replace it with safer placeholder data "
            f"or add '{ALLOW_COMMENT}' on that line."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
