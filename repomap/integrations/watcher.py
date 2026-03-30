"""File watcher for incremental symbol store updates.

Watches the repo for file changes and re-parses only changed files,
keeping the symbol store current without a full regeneration.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable


class RepomapWatcher:
    """Watches a directory tree and triggers incremental re-parses on change."""

    def __init__(
        self,
        engine,  # RepomapEngine instance
        on_update: Callable[[list[Path]], None] | None = None,
        debounce_seconds: float = 0.5,
    ) -> None:
        self._engine = engine
        self._on_update = on_update
        self._debounce = debounce_seconds
        self._observer = None
        self._pending: set[Path] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def start(self) -> None:
        """Start the file watcher (non-blocking, runs in background thread)."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            watcher = self

            class _Handler(FileSystemEventHandler):
                def on_modified(self, event):
                    if not event.is_directory:
                        watcher._queue(Path(event.src_path))

                def on_created(self, event):
                    if not event.is_directory:
                        watcher._queue(Path(event.src_path))

                def on_moved(self, event):
                    if not event.is_directory:
                        watcher._queue(Path(event.dest_path))

            self._observer = Observer()
            self._observer.schedule(
                _Handler(),
                str(self._engine.repo_root),
                recursive=True,
            )
            self._observer.start()
        except ImportError:
            raise RuntimeError(
                "watchdog is required for file watching. Install it with: pip install watchdog"
            )

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _queue(self, path: Path) -> None:
        """Queue a changed file, debouncing rapid successive changes."""
        # Only watch files the parser supports
        engine = self._engine
        if not (
            engine._ts_parser.supports(path)
            or engine._fallback_parser.supports(path)
        ):
            return
        if engine._is_excluded(str(path.relative_to(engine.repo_root))):
            return

        with self._lock:
            self._pending.add(path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Process all pending changed files."""
        with self._lock:
            changed = list(self._pending)
            self._pending.clear()
            self._timer = None

        if not changed:
            return

        t0 = time.monotonic()
        engine = self._engine
        for fp in changed:
            if not fp.exists():
                # File deleted — remove from store
                with engine.store._conn:
                    engine.store._conn.execute(
                        "DELETE FROM symbols WHERE file_path = ?", (str(fp),)
                    )
                continue
            if engine._ts_parser.supports(fp):
                symbols = engine._ts_parser.parse(fp)
            elif engine._fallback_parser.supports(fp):
                symbols = engine._fallback_parser.parse(fp)
            else:
                continue
            if symbols is not None:
                engine.store.upsert_file_symbols(fp, symbols)

        # Re-resolve edges for changed files
        from repomap.graph.resolver import ReferenceResolver
        resolver = ReferenceResolver(engine.store, engine.repo_root)
        resolver.resolve_all()

        if self._on_update:
            self._on_update(changed)

    def run_forever(self) -> None:
        """Start watcher and block until KeyboardInterrupt."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
