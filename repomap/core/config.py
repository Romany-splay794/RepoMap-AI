"""Configuration loader for RepoMap.

Precedence (highest first): CLI flags → .repomaprc → pyproject.toml [tool.repomap] → defaults.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_EXCLUDES = [
    "**/__pycache__/**",
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/build/**",
    "**/.venv/**",
    "**/venv/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/coverage/**",
    "**/.repomap/**",
    "**/*.md",
    "**/*.rst",
    "**/*.txt",
]


@dataclass
class RepomapConfig:
    max_tokens: int = 1000
    output_format: str = "markdown"    # markdown | json | xml | all
    db_path: Path = field(default_factory=lambda: Path(".repomap/symbols.db"))
    exclude_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_EXCLUDES))
    languages: list[str] = field(
        default_factory=lambda: ["python", "typescript", "javascript"]
    )
    tier: str = "auto"                 # auto | 1 | 2 | 3
    fallback_parser: bool = True       # use regex fallback for unknown languages

    @classmethod
    def load(cls, repo_root: Path) -> "RepomapConfig":
        """Load config from .repomaprc or pyproject.toml in repo_root."""
        cfg: dict = {}

        # Try pyproject.toml first
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            cfg = data.get("tool", {}).get("repomap", {})

        # .repomaprc overrides pyproject.toml
        repomaprc = repo_root / ".repomaprc"
        if repomaprc.exists():
            with open(repomaprc, "rb") as f:
                cfg.update(tomllib.load(f))

        inst = cls()
        if "max_tokens" in cfg:
            inst.max_tokens = int(cfg["max_tokens"])
        if "output_format" in cfg:
            inst.output_format = str(cfg["output_format"])
        if "db_path" in cfg:
            inst.db_path = Path(cfg["db_path"])
        if "exclude_patterns" in cfg:
            inst.exclude_patterns = list(cfg["exclude_patterns"])
        if "languages" in cfg:
            inst.languages = list(cfg["languages"])
        if "tier" in cfg:
            inst.tier = str(cfg["tier"])
        if "fallback_parser" in cfg:
            inst.fallback_parser = bool(cfg["fallback_parser"])

        return inst
