#!/usr/bin/env python3
"""Presence-only check for Hermes inference env names (never prints values)."""

from __future__ import annotations

import argparse
from pathlib import Path

KEYS = [
    "INFERENCE_BACKEND",
    "INFERENCE_BASE_URL",
    "INFERENCE_API_KEY",
    "INFERENCE_MODEL",
    "LM_STUDIO_BASE_URL",
    "LM_STUDIO_API_KEY",
    "LM_STUDIO_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_API_KEY",
    "OLLAMA_MODEL",
    "HERMES_API_KEY",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("env_file", nargs="?", default=".env")
    args = parser.parse_args()
    path = Path(args.env_file)
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    print(f"file={'present' if path.is_file() else 'missing'}: {path}")
    for key in KEYS:
        present = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(key + "=") and len(s.split("=", 1)[1].strip()) > 0:
                present = True
                break
        print(f"{key}: {'SET' if present else 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
