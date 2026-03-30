"""RepoMap CLI — entry point for the `repomap` command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(
    name="repomap",
    help="Token-efficient repository mapping tool for AI IDEs.",
    add_completion=False,
)
console = Console(stderr=True)


@app.command("generate")
def generate(
    path: Path = typer.Argument(
        default=Path("."),
        help="Repository root or directory to map.",
        exists=True,
    ),
    around: Optional[str] = typer.Option(
        None, "--around", "-a",
        help="Focus map around this function or class name.",
    ),
    scope: Optional[Path] = typer.Option(
        None, "--scope", "-s",
        help="Limit parsing to this subdirectory.",
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f",
        help="Output format: markdown | json | xml | all",
    ),
    max_tokens: int = typer.Option(
        1000, "--max-tokens", "-t",
        help="Maximum token budget for output.",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Write output to this file (default: stdout).",
    ),
    db: Optional[Path] = typer.Option(
        None, "--db",
        help="Symbol database path (default: .repomap/symbols.db).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show parse statistics.",
    ),
    narratives: bool = typer.Option(
        False, "--narratives",
        help="Include heuristic module narrative summaries.",
    ),
    hot_paths: bool = typer.Option(
        False, "--hot-paths",
        help="Annotate hot path functions (high entry-point traffic).",
    ),
    prepend: bool = typer.Option(
        False, "--prepend",
        help="Wrap XML output in <repository_context> for system prompts.",
    ),
    enrich: Optional[str] = typer.Option(
        None, "--enrich",
        help="LLM backend for enriched summaries: ollama | anthropic | openai",
    ),
) -> None:
    """Generate a token-efficient map of the repository."""
    from repomap.core.config import RepomapConfig
    from repomap.core.engine import RepomapEngine

    repo_root = path.resolve()
    config = RepomapConfig.load(repo_root)
    config.max_tokens = max_tokens
    if format != "markdown":
        config.output_format = format
    if db is not None:
        config.db_path = db

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Indexing repository...", total=None)
        engine = RepomapEngine(repo_root=repo_root, config=config)
        try:
            if format == "all":
                results = engine.generate_all_formats(
                    scope=scope, around=around, max_tokens=max_tokens
                )
                progress.stop()
                for fmt_name, result in results.items():
                    if output:
                        suffix = {"markdown": ".md", "json": ".json", "xml": ".xml"}[fmt_name]
                        out_path = output.with_suffix(suffix)
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text(result.text, encoding="utf-8")
                        if verbose:
                            console.print(
                                f"[green]✓[/] {fmt_name}: {out_path} "
                                f"({result.tokens_used} tokens)"
                            )
                    else:
                        typer.echo(f"\n{'='*60}\n# Format: {fmt_name}\n{'='*60}")
                        typer.echo(result.text)
            else:
                # Force XML format when --prepend is used
                if prepend and format == "markdown":
                    config.output_format = "xml"
                result = engine.generate(
                    scope=scope, around=around, max_tokens=max_tokens,
                    narratives=narratives, hot_paths=hot_paths,
                    prepend=prepend, enrich=enrich,
                )
                progress.stop()
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(result.text, encoding="utf-8")
                    console.print(
                        f"[green]✓[/] Written to [bold]{output}[/] "
                        f"({result.tokens_used} tokens, "
                        f"{result.symbols_shown}/{result.total_symbols} symbols)"
                    )
                else:
                    typer.echo(result.text)

            if verbose and format != "all":
                console.print(
                    f"\n[dim]Stats:[/] {result.files_stale} files re-parsed | "
                    f"{result.stats.get('symbols', 0)} symbols | "
                    f"{result.stats.get('edges', 0)} edges | "
                    f"{result.stats.get('unresolved_edges', 0)} unresolved"
                )
        finally:
            engine.close()


@app.command("stats")
def stats(
    path: Path = typer.Argument(default=Path("."), help="Repository root."),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Show symbol store statistics."""
    from repomap.core.config import RepomapConfig
    from repomap.core.symbol_store import SymbolStore

    repo_root = path.resolve()
    config = RepomapConfig.load(repo_root)
    if db:
        config.db_path = db
    db_path = config.db_path if config.db_path.is_absolute() else repo_root / config.db_path

    if not db_path.exists():
        console.print("[yellow]No symbol database found. Run `repomap generate` first.[/]")
        raise typer.Exit(1)

    store = SymbolStore(db_path)
    s = store.stats()
    store.close()

    typer.echo(f"Symbols:          {s['symbols']}")
    typer.echo(f"Edges:            {s['edges']}")
    typer.echo(f"Unresolved edges: {s['unresolved_edges']}")
    typer.echo(f"Data models:      {s['data_models']}")


@app.command("visual")
def visual(
    path: Path = typer.Argument(default=Path("."), help="Repository root."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output HTML file path."),
    max_nodes: int = typer.Option(2000, "--max-nodes", help="Max symbols to include in visual."),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Generate a self-contained interactive HTML visual explorer."""
    from repomap.core.config import RepomapConfig
    from repomap.core.engine import RepomapEngine
    from repomap.graph.builder import GraphBuilder
    from repomap.graph.backends.networkx_backend import build_nx_graph
    from repomap.graph.ranker import GraphRanker
    from repomap.visual.generator import generate_html

    repo_root = path.resolve()
    config = RepomapConfig.load(repo_root)
    if db:
        config.db_path = db

    out_path = output or (repo_root / ".repomap.html")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as progress:
        progress.add_task("Building graph...", total=None)
        engine = RepomapEngine(repo_root=repo_root, config=config)
        try:
            # Run a full generate pass to ensure index is up to date
            engine.generate(max_tokens=100000)
            from repomap.graph.builder import GraphBuilder
            builder = GraphBuilder(engine.store)
            nodes, edges = builder.build_from_store()
            graph = build_nx_graph(nodes, edges)
            ranker = GraphRanker()
            ranker.apply_scores(nodes, ranker.rank(graph))
        finally:
            engine.close()

    html = generate_html(
        nodes, edges,
        repo_root=str(repo_root),
        repo_name=repo_root.name,
        max_nodes=max_nodes,
    )
    out_path.write_text(html, encoding="utf-8")
    size_kb = round(len(html.encode()) / 1024)
    console.print(
        f"[green]✓[/] Visual explorer written to [bold]{out_path}[/] "
        f"({size_kb} KB, {len(nodes)} symbols, {len(edges)} edges)"
    )
    console.print(f"[dim]Open in any browser or IDE preview panel.[/]")


@app.command("watch")
def watch(
    path: Path = typer.Argument(default=Path("."), help="Repository root to watch."),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Watch the repository for changes and update the symbol store incrementally."""
    from repomap.core.config import RepomapConfig
    from repomap.core.engine import RepomapEngine
    from repomap.integrations.watcher import RepomapWatcher

    repo_root = path.resolve()
    config = RepomapConfig.load(repo_root)
    if db:
        config.db_path = db

    # Initial index
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as progress:
        progress.add_task("Initial indexing...", total=None)
        engine = RepomapEngine(repo_root=repo_root, config=config)
        engine.generate(max_tokens=100000)

    def on_update(changed_files: list[Path]) -> None:
        names = ", ".join(f.name for f in changed_files[:3])
        if len(changed_files) > 3:
            names += f" (+{len(changed_files) - 3} more)"
        console.print(f"[dim]↻ Updated {names}[/]")

    watcher = RepomapWatcher(engine, on_update=on_update)
    console.print(f"[green]Watching[/] {repo_root} for changes. Press Ctrl+C to stop.")
    try:
        watcher.run_forever()
    finally:
        engine.close()


@app.command("serve")
def serve(
    path: Path = typer.Argument(default=Path("."), help="Repository root."),
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio | http"),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP host (http transport only)."),
    port: int = typer.Option(3847, "--port", "-p", help="HTTP port (http transport only)."),
) -> None:
    """Start the RepoMap MCP server."""
    from repomap.integrations.mcp_server import run_stdio, run_http

    repo_root = str(path.resolve())
    if transport == "stdio":
        run_stdio(repo_root=repo_root)
    elif transport == "http":
        console.print(f"[green]Starting RepoMap MCP server at http://{host}:{port}/mcp[/]")
        run_http(host=host, port=port, repo_root=repo_root)
    else:
        console.print(f"[red]Unknown transport: {transport}. Use 'stdio' or 'http'.[/]")
        raise typer.Exit(1)


@app.command("init")
def init(
    path: Path = typer.Argument(default=Path("."), help="Repository root."),
) -> None:
    """Generate IDE config files for MCP integration."""
    repo_root = path.resolve()
    import shutil

    repomap_exe = shutil.which("repomap") or "repomap"

    # Cursor
    cursor_dir = repo_root / ".cursor"
    cursor_dir.mkdir(exist_ok=True)
    cursor_cfg = cursor_dir / "mcp.json"
    cursor_cfg.write_text(
        f'{{"mcpServers":{{"repomap":{{"command":"{repomap_exe}","args":["serve","--transport","stdio"]}}}}}}\n',
        encoding="utf-8",
    )

    # VS Code
    vscode_dir = repo_root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    vscode_cfg = vscode_dir / "mcp.json"
    vscode_cfg.write_text(
        f'{{"servers":{{"repomap":{{"type":"stdio","command":"{repomap_exe}","args":["serve","--transport","stdio"]}}}}}}\n',
        encoding="utf-8",
    )

    # .repomap config
    repomap_dir = repo_root / ".repomap"
    repomap_dir.mkdir(exist_ok=True)

    console.print(f"[green]✓[/] Generated .cursor/mcp.json")
    console.print(f"[green]✓[/] Generated .vscode/mcp.json")

    # Claude Desktop (global config)
    import platform, json as _json
    if platform.system() == "Darwin":
        claude_cfg_dir = Path.home() / "Library" / "Application Support" / "Claude"
    elif platform.system() == "Windows":
        claude_cfg_dir = Path.home() / "AppData" / "Roaming" / "Claude"
    else:
        claude_cfg_dir = Path.home() / ".config" / "claude"

    claude_cfg_file = claude_cfg_dir / "claude_desktop_config.json"
    if claude_cfg_dir.exists():
        # Merge into existing config rather than overwriting
        existing = {}
        if claude_cfg_file.exists():
            try:
                existing = _json.loads(claude_cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.setdefault("mcpServers", {})
        existing["mcpServers"]["repomap"] = {
            "command": repomap_exe,
            "args": ["serve", "--transport", "stdio", str(repo_root)],
        }
        claude_cfg_file.write_text(_json.dumps(existing, indent=2), encoding="utf-8")
        console.print(f"[green]✓[/] Updated Claude Desktop config at {claude_cfg_file}")
    else:
        console.print(
            f"[dim]Claude Desktop not detected — to add manually, see README.[/]"
        )

    console.print(f"\n[bold green]Setup complete![/] RepoMap MCP is ready for:")
    console.print(f"  • Cursor (restart to pick up .cursor/mcp.json)")
    console.print(f"  • VS Code with Copilot (restart to pick up .vscode/mcp.json)")
    if claude_cfg_dir.exists():
        console.print(f"  • Claude Desktop (restart the app)")


@app.command("diff")
def diff(
    ref: str = typer.Argument(
        default="HEAD~1",
        help="Git ref to diff against (e.g., HEAD~1, main, abc123).",
    ),
    path: Path = typer.Argument(default=Path("."), help="Repository root."),
    depth: int = typer.Option(
        2, "--depth", "-d",
        help="Blast radius depth (BFS hops from changed symbols).",
    ),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Show changed symbols and their blast radius since a git ref."""
    from repomap.core.config import RepomapConfig
    from repomap.core.engine import RepomapEngine
    from repomap.integrations.diff import compute_diff, format_blast_radius

    repo_root = path.resolve()
    config = RepomapConfig.load(repo_root)
    if db:
        config.db_path = db

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Analyzing diff...", total=None)
        engine = RepomapEngine(repo_root=repo_root, config=config)
        try:
            # Ensure index is up to date
            engine.generate(max_tokens=100000)
            br = compute_diff(repo_root, engine.store, ref=ref, depth=depth)
        finally:
            engine.close()

    typer.echo(format_blast_radius(br))


if __name__ == "__main__":
    app()
