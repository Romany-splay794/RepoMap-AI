# RepoMap

[![PyPI](https://img.shields.io/pypi/v/repomap-ai?label=pip&color=blue)](https://pypi.org/project/repomap-ai/)
[![npm](https://img.shields.io/npm/v/repomap-ai?label=npm&color=red)](https://www.npmjs.com/package/repomap-ai)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Build faster with AI — without hitting context limits

You've felt this: you're using Cursor, Claude, or Copilot on a real codebase. You ask it to refactor something. It confidently touches the wrong file, misses a dependency three folders away, or invents a function that already exists somewhere else. You spend more time correcting the AI than writing code.

**The root cause: your AI doesn't know your codebase.** It only sees what fits in its context window — usually a few open files. The moment your project grows beyond a handful of files, the AI starts guessing.

RepoMap fixes this by giving your AI a **structured map of your entire codebase** — compressed into ~1000 tokens. It's not raw source code. It's a ranked, dependency-aware index of every function, class, and their relationships, with the most important ones surfaced first.

### What this means in practice

| Without RepoMap | With RepoMap |
|-----------------|--------------|
| AI sees 2–3 open files | AI knows the structure of the entire repo |
| Hallucinates function names | References real symbols and their signatures |
| Misses cross-file dependencies | Understands what calls what, what imports what |
| Needs constant copy-pasting of context | MCP server feeds context automatically on demand |
| Gets confused on large codebases | Scales to 10k+ symbols via PageRank ranking |

### The workflow

```
1. Install RepoMap              →  pip install repomap-ai
2. Set up MCP in your IDE       →  repomap init .   (auto-configures Cursor, VS Code, Claude Desktop)
3. Open your AI assistant       →  Ask anything about your codebase
4. AI calls RepoMap tools       →  Gets accurate, token-efficient context automatically
```

Your AI assistant now knows:
- Which functions exist and where they live
- What calls what (the full call graph)
- Which symbols are most important (PageRank score)
- Where your API routes, CLI commands, and data models are
- What changes when you modify a specific function (blast radius)

You stop correcting hallucinations. You start shipping.

---



- [Features](#features)
- [Installation](#installation)
  - [Via pip](#via-pip)
  - [Via npm / npx](#via-npm--npx)
  - [From source](#from-source-development)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [MCP Setup](#mcp-setup)
  - [One-command setup](#one-command-setup)
  - [Cursor](#cursor)
  - [VS Code](#vs-code)
  - [Claude Desktop](#claude-desktop)
  - [MCP Tools](#mcp-tools)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- 🌳 **Tree-sitter parsing** for Python, TypeScript, JavaScript (Go, Rust, Java, Ruby, C/C++ via extras)
- 🔗 **Typed dependency graph** — `calls`, `imports`, `reads`, `writes`, `extends`, `implements`
- 📊 **PageRank ranking** to surface the most important symbols first
- 💰 **Token-budget-aware output** — never exceeds your configured limit
- 🎯 **Data model detection** — Pydantic, dataclass, SQLAlchemy
- 🚪 **Entry point detection** — CLI commands, API routes, `main()` functions
- 📄 **Multiple output formats** — Markdown, JSON, XML
- 🗺️ **Interactive HTML visual explorer** with WebGL rendering (handles 10k+ nodes)
- 🤖 **MCP server** for Cursor, VS Code, Claude Desktop
- 👁️ **Incremental file watcher** — updates the map as you code

---

## Installation

### Via pip

Requires Python 3.11+.

```bash
pip install repomap-ai
```

With optional extras:

```bash
# Full install: visual explorer + MCP server + performance backend
pip install "repomap-ai[visual,mcp,scale]"

# Additional language support (Go, Rust, Java, Ruby, C/C++)
pip install "repomap-ai[languages]"
```

Recommended for global CLI use:

```bash
pipx install repomap-ai
```

Verify installation:

```bash
repomap --help
```

---

### Via npm / npx

No Python setup needed — the npm package auto-installs the Python backend on first run.

```bash
# Run instantly without installing anything globally
npx repomap-ai generate .

# Or install globally to get the `repomap` command
npm install -g repomap-ai
repomap generate .
```

> **Note:** Python 3.11+ must still be available on your `PATH`. The npm package is a thin wrapper that auto-runs `pip install repomap-ai` on install.

---

### From source (development)

```bash
git clone https://github.com/tushar22/repomap.git
cd repomap

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install in editable mode with all dev extras
pip install -e ".[dev,visual,mcp,scale,languages]"

# Run tests
pytest tests/ -v
```

---

## Quick Start

```bash
# cd into any repository
cd /path/to/your/project

# Generate a token-efficient map (outputs to stdout)
repomap generate .

# Save to file with a larger token budget
repomap generate . --max-tokens 4000 --output map.md

# Focus on a specific function and its dependencies
repomap generate . --around "UserService.authenticate"

# Open the interactive visual graph in your browser
repomap visual . -o graph.html && open graph.html

# Set up MCP for your AI IDE (one command)
repomap init .
```

---

## CLI Reference

### `repomap generate`

Generate a token-efficient repository map.

```bash
repomap generate [PATH] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--max-tokens N` | `1000` | Token budget for output |
| `--around SYMBOL` | — | Focus map around a specific symbol name |
| `--format FORMAT` | `markdown` | Output format: `markdown`, `json`, `xml`, `all` |
| `--output FILE` | stdout | Write output to a file |
| `--scope PATH` | — | Limit parsing to a subdirectory |
| `--verbose` | `false` | Show parse statistics |
| `--narratives` | `false` | Include heuristic module summaries |
| `--hot-paths` | `false` | Annotate high-traffic entry-point functions |
| `--prepend` | `false` | Wrap XML in `<repository_context>` for system prompts |

**Examples:**

```bash
# Default: markdown, 1000 tokens
repomap generate .

# JSON output focused on a class
repomap generate . --format json --around "PaymentService" --output context.json

# Scoped to a subdirectory, XML format for Claude
repomap generate . --scope src/api --format xml --max-tokens 4000
```

---

### `repomap init`

Generate IDE config files for MCP integration. Supports Cursor, VS Code, and Claude Desktop in one command.

```bash
repomap init [PATH]
```

This auto-creates:
- `.cursor/mcp.json` — for Cursor
- `.vscode/mcp.json` — for VS Code / GitHub Copilot
- `~/Library/Application Support/Claude/claude_desktop_config.json` — for Claude Desktop (if installed)

---

### `repomap serve`

Start the MCP server.

```bash
# stdio transport (used by Cursor, VS Code, Claude Desktop)
repomap serve . --transport stdio

# HTTP transport (for tools that support SSE)
repomap serve . --transport http --port 3847
```

---

### `repomap visual`

Generate a self-contained interactive HTML graph explorer (WebGL-accelerated, handles 10k+ symbols).

```bash
repomap visual . -o graph.html
```

Open the HTML file in any browser — no server needed.

---

### `repomap watch`

Incrementally update the symbol store as files change.

```bash
repomap watch .
```

---

### `repomap stats`

Show symbol store statistics.

```bash
repomap stats .
```

---

### `repomap diff`

Show changed symbols and their blast radius (affected callers/dependents) since a git ref.

```bash
repomap diff HEAD~1 .
repomap diff main . --depth 3
```

---

## MCP Setup

RepoMap runs as a **local MCP server** — your code never leaves your machine.

### One-command setup

```bash
# Install
pip install repomap-ai
# or: npm install -g repomap-ai

# cd into your project
cd /path/to/your/project

# Auto-configure all supported IDEs at once
repomap init .
```

Then restart your IDE. Done.

---

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "repomap": {
      "command": "repomap",
      "args": ["serve", ".", "--transport", "stdio"]
    }
  }
}
```

Restart Cursor. The MCP tools will appear in the AI panel.

---

### VS Code

Add to `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "repomap": {
      "type": "stdio",
      "command": "repomap",
      "args": ["serve", ".", "--transport", "stdio"]
    }
  }
}
```

Restart VS Code. Works with GitHub Copilot and any MCP-compatible extension.

---

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "repomap": {
      "command": "repomap",
      "args": ["serve", "--transport", "stdio", "/path/to/your/project"]
    }
  }
}
```

Windows path: `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop.

---

### MCP Tools

Once connected, your AI assistant has access to these tools:

| Tool | Description |
|------|-------------|
| `repomap_overview` | Token-budgeted overview of the entire repository |
| `repomap_around` | Explore symbols surrounding a specific function or class |
| `repomap_query` | Search symbols by name or pattern |
| `repomap_data_models` | List detected data models (Pydantic, dataclass, SQLAlchemy) |
| `repomap_entry_points` | List detected entry points (routes, CLI commands, `main`) |
| `repomap_impact` | Analyze blast radius of changing a specific symbol |

---

## Configuration

RepoMap reads config from `pyproject.toml` or `.repomaprc` at the repository root.

### pyproject.toml

```toml
[tool.repomap]
max_tokens = 1000
output_format = "markdown"
exclude_patterns = ["**/node_modules/**", "**/.venv/**", "**/.git/**"]
```

### .repomaprc

```ini
max_tokens = 1000
output_format = markdown
exclude_patterns = **/node_modules/**, **/.venv/**, **/.git/**
```

| Key | Default | Description |
|-----|---------|-------------|
| `max_tokens` | `1000` | Default token budget |
| `output_format` | `markdown` | Default output format |
| `exclude_patterns` | `[]` | Glob patterns to skip |

---

## Architecture

```
Source Files → Parser → Symbol Store → Graph Builder → PageRank → Formatter → Output
```

1. **Parser** — tree-sitter grammars extract symbols (functions, classes, methods) and typed edges from source files. Results are cached in `.repomap/symbols.db`.

2. **Graph** — directed dependency graph built with NetworkX. Edges are typed (`calls`, `imports`, `reads`, `writes`, `extends`, `implements`) and weighted by confidence.

3. **Ranker** — PageRank over the dependency graph scores each symbol by structural importance. Entry points and data models receive rank boosts.

4. **Formatter** — ranked symbols serialized to Markdown/JSON/XML, pruned to fit within the token budget using tiktoken for accurate counting.

---

## Contributing

Contributions are welcome! Here's how to get started.

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/repomap.git
cd repomap
```

### 2. Set up your dev environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,visual,mcp,scale]"
```

### 3. Run the tests

```bash
pytest tests/ -v
```

All tests must pass before submitting a PR.

### 4. Make your changes

- **Bug fixes** — open a PR directly with a clear description
- **New features** — open an issue first to discuss the approach
- **New language support** — add a tree-sitter query file under `repomap/parser/queries/` and register it in `tree_sitter_parser.py`

### 5. Code style

- Follow PEP 8 (enforced by `ruff` if you have it installed)
- Type annotations on all public functions
- Docstrings for new public classes and methods

### 6. Submit a Pull Request

- Target the `main` branch
- Describe what changed and why
- Reference any related issues (`Fixes #123`)

### Project structure

```
repomap/
├── parser/          # Tree-sitter parsers + .scm query files per language
├── graph/           # Graph builder, models, PageRank ranker
├── formatter/       # Markdown, JSON, XML output formatters
├── core/            # Engine, config, symbol store (SQLite)
├── integrations/    # CLI (Typer), MCP server, file watcher, diff
├── visual/          # WebGL HTML explorer generator + template
├── intelligence/    # LLM enrichment, hot path detection, narratives
└── data_models/     # Pydantic/dataclass/SQLAlchemy detector
tests/
npm/                 # npm wrapper package
```

### Reporting bugs

Open an issue at [github.com/tushar22/repomap/issues](https://github.com/tushar22/repomap/issues) with:
- Your OS and Python version
- The command you ran
- The full error output

---

## License

MIT — see [LICENSE](LICENSE) for details.
