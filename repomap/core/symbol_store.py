"""SQLite-backed persistent symbol store with WAL mode."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from repomap.parser.base import Symbol, SymbolKind


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    signature TEXT DEFAULT '',
    language TEXT DEFAULT '',
    file_mtime REAL,
    is_entry_point BOOLEAN DEFAULT 0,
    is_exported BOOLEAN DEFAULT 1,
    decorators_json TEXT DEFAULT '[]',
    bases_json TEXT DEFAULT '[]',
    imports_json TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    target_qualified_name TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS data_models (
    id INTEGER PRIMARY KEY,
    symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    framework TEXT,
    fields_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_target_name ON edges(target_qualified_name);
"""


class SymbolStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ─── File staleness ───────────────────────────────────────────────────────

    def get_stale_files(self, file_paths: list[Path]) -> list[Path]:
        """Return files that are new or have a newer mtime than stored."""
        stale: list[Path] = []
        cur = self._conn.cursor()
        for fp in file_paths:
            try:
                current_mtime = os.stat(fp).st_mtime
            except OSError:
                continue
            row = cur.execute(
                "SELECT file_mtime FROM symbols WHERE file_path = ? LIMIT 1",
                (str(fp),),
            ).fetchone()
            if row is None or row["file_mtime"] != current_mtime:
                stale.append(fp)
        return stale

    # ─── Upsert ───────────────────────────────────────────────────────────────

    def upsert_file_symbols(self, file_path: Path, symbols: list[Symbol]) -> None:
        """Replace all symbols for a file atomically."""
        try:
            mtime = os.stat(file_path).st_mtime
        except OSError:
            mtime = 0.0

        with self._conn:
            self._conn.execute(
                "DELETE FROM symbols WHERE file_path = ?", (str(file_path),)
            )
            for sym in symbols:
                if sym.kind == SymbolKind.IMPORT:
                    continue  # imports stored indirectly via edges
                cur = self._conn.execute(
                    """
                    INSERT INTO symbols
                        (name, qualified_name, kind, file_path, line_start, line_end,
                         signature, language, file_mtime, is_entry_point, is_exported,
                         decorators_json, bases_json, imports_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        sym.name,
                        sym.qualified_name,
                        str(sym.kind),
                        str(sym.file_path),
                        sym.line_start,
                        sym.line_end,
                        sym.signature,
                        sym.language,
                        mtime,
                        int(sym.is_entry_point),
                        int(sym.is_exported),
                        json.dumps(sym.decorators),
                        json.dumps(sym.bases),
                        json.dumps(sym.imports),
                    ),
                )
                symbol_id = cur.lastrowid
                # Store call-references as pending edges
                for ref_name in sym.references:
                    self._conn.execute(
                        """
                        INSERT INTO edges (source_id, target_qualified_name, edge_type, confidence)
                        VALUES (?, ?, 'calls', 1.0)
                        """,
                        (symbol_id, ref_name),
                    )
                # Store inheritance edges
                for base in sym.bases:
                    self._conn.execute(
                        """
                        INSERT INTO edges (source_id, target_qualified_name, edge_type, confidence)
                        VALUES (?, ?, 'extends', 1.0)
                        """,
                        (symbol_id, base),
                    )

    def insert_edge(
        self,
        source_id: int,
        target_id: int | None,
        target_qualified_name: str,
        edge_type: str,
        confidence: float = 1.0,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO edges
                    (source_id, target_id, target_qualified_name, edge_type, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source_id, target_id, target_qualified_name, edge_type, confidence),
            )

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_all_symbols(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM symbols").fetchall()

    def get_all_edges(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM edges").fetchall()

    def get_unresolved_edges(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM edges WHERE target_id IS NULL"
        ).fetchall()

    def get_symbol_by_id(self, symbol_id: int) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM symbols WHERE id = ?", (symbol_id,)
        ).fetchone()

    def get_symbols_by_name(self, name: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM symbols WHERE name = ?", (name,)
        ).fetchall()

    def get_symbol_by_qualified_name(self, qname: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM symbols WHERE qualified_name = ?", (qname,)
        ).fetchone()

    def get_symbols_for_file(self, file_path: Path) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM symbols WHERE file_path = ?", (str(file_path),)
        ).fetchall()

    def get_imports_for_file(self, file_path: Path) -> list[dict]:
        """Return stored import lists for all symbols in a file."""
        rows = self.get_symbols_for_file(file_path)
        result: list[dict] = []
        for row in rows:
            imports = json.loads(row["imports_json"] or "[]")
            result.extend(imports)
        return result

    # ─── Edge resolution ──────────────────────────────────────────────────────

    def resolve_edge(self, edge_id: int, target_id: int, confidence: float) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE edges SET target_id = ?, confidence = ? WHERE id = ?",
                (target_id, confidence, edge_id),
            )

    def update_edge_confidence(self, edge_id: int, confidence: float) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE edges SET confidence = ? WHERE id = ?",
                (confidence, edge_id),
            )

    # ─── Data model storage ───────────────────────────────────────────────────

    def upsert_data_model(
        self, symbol_id: int, framework: str, fields: list[dict]
    ) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM data_models WHERE symbol_id = ?", (symbol_id,)
            )
            self._conn.execute(
                "INSERT INTO data_models (symbol_id, framework, fields_json) VALUES (?,?,?)",
                (symbol_id, framework, json.dumps(fields)),
            )

    def get_all_data_models(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT dm.*, s.name, s.qualified_name, s.file_path, s.line_start
            FROM data_models dm
            JOIN symbols s ON s.id = dm.symbol_id
            """
        ).fetchall()

    def get_data_model_by_name(self, name: str) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT dm.*, s.name, s.qualified_name, s.file_path, s.line_start
            FROM data_models dm
            JOIN symbols s ON s.id = dm.symbol_id
            WHERE s.name = ?
            """,
            (name,),
        ).fetchone()

    # ─── Entry point update ───────────────────────────────────────────────────

    def mark_entry_point(self, symbol_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE symbols SET is_entry_point = 1 WHERE id = ?", (symbol_id,)
            )

    # ─── Stats ────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        cur = self._conn
        n_symbols = cur.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        n_edges = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        n_unresolved = cur.execute(
            "SELECT COUNT(*) FROM edges WHERE target_id IS NULL"
        ).fetchone()[0]
        n_models = cur.execute("SELECT COUNT(*) FROM data_models").fetchone()[0]
        return {
            "symbols": n_symbols,
            "edges": n_edges,
            "unresolved_edges": n_unresolved,
            "data_models": n_models,
        }
