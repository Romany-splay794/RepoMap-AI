# repomap-ai

> Token-efficient repository mapping tool for AI IDEs — npm wrapper for the [repomap](https://pypi.org/project/repomap/) Python package.

RepoMap parses source code with tree-sitter, builds function-level dependency graphs, and outputs compact maps that fit within LLM token budgets. Works with Cursor, VS Code, and any MCP-compatible AI IDE.

## Requirements

- **Node.js** >= 16
- **Python** >= 3.11 (with pip)

## Usage

### One-time use (no install)

```bash
npx repomap-ai generate .
```

### Global install

```bash
npm install -g repomap-ai
repomap generate .
```

### Or install via pip directly

```bash
pip install repomap
repomap generate .
```

## Quick Start

```bash
# Generate a map of any repository
npx repomap-ai generate /path/to/your/repo

# Or if you're already inside the repo
cd /path/to/your/repo
npx repomap-ai generate .

# With a larger token budget, JSON format
npx repomap-ai generate . --max-tokens 4000 --format json

# Set up MCP integration for Cursor / VS Code
npx repomap-ai init .
```

## Commands

| Command | Description |
|---|---|
| `repomap generate .` | Generate a token-budgeted map of the repository |
| `repomap visual . -o map.html` | Interactive HTML dependency graph |
| `repomap stats .` | Symbol and edge statistics |
| `repomap watch .` | Incremental file watcher |
| `repomap serve . --transport stdio` | Start MCP server for IDE integration |
| `repomap init .` | Generate `.cursor/mcp.json` and `.vscode/mcp.json` |

## MCP Integration (Cursor / VS Code)

Run `repomap init .` in your repo root to auto-generate config files, then restart your IDE.

Or add manually to `.cursor/mcp.json`:

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

## How It Works

This npm package is a thin wrapper. When you run `npx repomap-ai`, it:

1. Checks if the `repomap` Python CLI is installed
2. If not, runs `pip install repomap` automatically
3. Delegates all commands to the Python CLI

The actual implementation lives in the [`repomap` PyPI package](https://pypi.org/project/repomap/).

## License

MIT
