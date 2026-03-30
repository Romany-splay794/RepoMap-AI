"""Optional LLM enrichment for module summaries and function annotations."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any


class LLMCache:
    """SQLite-based cache for LLM responses, keyed by content hash."""

    def __init__(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = cache_dir / "llm_cache.db"
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(content_hash TEXT PRIMARY KEY, response TEXT, backend TEXT, created_at REAL)"
        )
        self._conn.commit()

    def get(self, content_hash: str) -> str | None:
        row = self._conn.execute(
            "SELECT response FROM cache WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row[0] if row else None

    def put(self, content_hash: str, response: str, backend: str) -> None:
        import time
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (content_hash, response, backend, created_at) "
            "VALUES (?, ?, ?, ?)",
            (content_hash, response, backend, time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class LLMEnricher:
    """Enrich module summaries and top-symbol annotations using an LLM backend."""

    def __init__(
        self,
        backend: str = "ollama",
        model: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.backend = backend
        self.model = model or self._default_model(backend)
        self._cache = LLMCache(cache_dir or Path(".repomap"))

    def _default_model(self, backend: str) -> str:
        if backend == "ollama":
            return "llama3.2"
        elif backend == "anthropic":
            return "claude-sonnet-4-20250514"
        elif backend == "openai":
            return "gpt-4o-mini"
        return "llama3.2"

    def enrich_module_summary(
        self,
        module_name: str,
        symbol_names: list[str],
        signatures: list[str],
        existing_heuristic: str = "",
    ) -> str:
        """Generate an LLM-enhanced summary for a module."""
        prompt = self._build_module_prompt(module_name, symbol_names, signatures, existing_heuristic)
        ch = content_hash(prompt)

        cached = self._cache.get(ch)
        if cached:
            return cached

        response = self._call_llm(prompt)
        if response:
            self._cache.put(ch, response, self.backend)
        return response or existing_heuristic

    def enrich_function_annotation(
        self,
        qualified_name: str,
        signature: str,
        references: list[str],
    ) -> str:
        """Generate a brief purpose annotation for a top-ranked function."""
        prompt = (
            f"In one sentence (max 15 words), describe the purpose of this function:\n"
            f"Name: {qualified_name}\n"
            f"Signature: {signature}\n"
        )
        if references:
            prompt += f"Calls: {', '.join(references[:10])}\n"
        prompt += "Reply with ONLY the one-sentence description, no preamble."

        ch = content_hash(prompt)
        cached = self._cache.get(ch)
        if cached:
            return cached

        response = self._call_llm(prompt)
        if response:
            # Clean up: take only the first sentence
            response = response.strip().split("\n")[0].rstrip(".")
            self._cache.put(ch, response, self.backend)
        return response or ""

    def close(self) -> None:
        self._cache.close()

    def _build_module_prompt(
        self,
        module_name: str,
        symbol_names: list[str],
        signatures: list[str],
        heuristic: str,
    ) -> str:
        prompt = (
            f"Summarize the purpose of this code module in one sentence (max 20 words).\n"
            f"Module: {module_name}\n"
        )
        if heuristic:
            prompt += f"Heuristic guess: {heuristic}\n"
        if signatures:
            prompt += "Key signatures:\n"
            for sig in signatures[:10]:
                prompt += f"  {sig}\n"
        elif symbol_names:
            prompt += f"Symbols: {', '.join(symbol_names[:15])}\n"
        prompt += "Reply with ONLY the one-sentence summary, no preamble."
        return prompt

    def _call_llm(self, prompt: str) -> str | None:
        if self.backend == "ollama":
            return self._call_ollama(prompt)
        elif self.backend == "anthropic":
            return self._call_anthropic(prompt)
        elif self.backend == "openai":
            return self._call_openai(prompt)
        return None

    def _call_ollama(self, prompt: str) -> str | None:
        try:
            import httpx
        except ImportError:
            try:
                import urllib.request
                import json as _json
                req = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=_json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read())
                    return data.get("response", "").strip()
            except Exception:
                return None

        try:
            resp = httpx.post(
                "http://localhost:11434/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception:
            return None

    def _call_anthropic(self, prompt: str) -> str | None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            import httpx
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"].strip()
        except Exception:
            return None

    def _call_openai(self, prompt: str) -> str | None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            import httpx
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None
