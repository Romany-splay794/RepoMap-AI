"""Data model detector: identifies data models across Python, TS, Go, Java, Rust, Ruby."""

from __future__ import annotations

import json
import re
from pathlib import Path

from repomap.core.symbol_store import SymbolStore

PYDANTIC_BASES = {"BaseModel", "BaseSettings", "GenericModel", "SQLModel", "RootModel"}
DATACLASS_DECORATORS = {"dataclass", "attrs.define", "attr.s", "attr.attrs"}
SQLALCHEMY_BASES = {"Base", "DeclarativeBase", "Model", "DeclarativeBaseNoMeta"}
DJANGO_BASES = {"Model", "forms.Form", "forms.ModelForm"}

# Java JPA/ORM annotations that mark a class as a data model
JAVA_DATA_ANNOTATIONS = {"Entity", "Table", "Document", "Data", "Value"}

# Ruby ActiveRecord and similar bases
RUBY_DATA_BASES = {"ActiveRecord::Base", "ApplicationRecord", "Sequel::Model", "Dry::Struct"}

# Rust derive macros that indicate a data model
RUST_DATA_DERIVES = {"Serialize", "Deserialize", "FromRow", "sqlx::FromRow", "Queryable", "Insertable"}


def _is_pydantic(bases: list[str], decorators: list[str]) -> bool:
    return any(b in PYDANTIC_BASES for b in bases)


def _is_dataclass(bases: list[str], decorators: list[str]) -> bool:
    for dec in decorators:
        # Strip @ and arguments
        dec_clean = dec.lstrip("@").split("(")[0].strip()
        if dec_clean in DATACLASS_DECORATORS:
            return True
    return False


def _is_sqlalchemy(bases: list[str], decorators: list[str]) -> bool:
    return any(b in SQLALCHEMY_BASES for b in bases)


def _extract_python_fields(file_path: str, class_name: str, line_start: int) -> list[dict]:
    """Heuristically extract annotated fields from a Python class body."""
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = source.splitlines()
    fields: list[dict] = []
    # Find the class body lines (crude but works for most cases)
    in_class = False
    class_indent: int | None = None
    body_indent: int | None = None
    for i, line in enumerate(lines):
        if i < line_start - 1:
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not in_class:
            if stripped.startswith(f"class {class_name}"):
                in_class = True
                class_indent = indent
            continue
        if class_indent is not None and stripped == "":
            continue
        if class_indent is not None and indent <= class_indent and stripped:
            break  # exited class
        if body_indent is None and stripped:
            body_indent = indent
        if body_indent is not None and indent == body_indent and ":" in stripped:
            # annotation line: field_name: Type [= default]
            m = re.match(r"(\w+)\s*:\s*([^=\n]+?)(?:\s*=.*)?$", stripped)
            if m:
                fname = m.group(1)
                ftype = m.group(2).strip()
                optional = "Optional" in ftype or ftype.startswith("Optional") or "| None" in ftype
                if fname not in ("__tablename__", "__abstract__"):
                    fields.append({"name": fname, "type": ftype, "optional": optional})
    return fields


class DataModelDetector:
    def __init__(self, store: SymbolStore) -> None:
        self._store = store

    def detect_and_store(self) -> int:
        """Detect data models among all CLASS symbols and store them. Returns count."""
        count = 0
        for row in self._store.get_all_symbols():
            if row["kind"] != "class":
                continue
            bases = json.loads(row["bases_json"] or "[]")
            decorators = json.loads(row["decorators_json"] or "[]")
            lang = row["language"] or ""

            framework: str | None = None
            if lang == "python":
                if _is_pydantic(bases, decorators):
                    framework = "pydantic"
                elif _is_dataclass(bases, decorators):
                    framework = "dataclass"
                elif _is_sqlalchemy(bases, decorators):
                    framework = "sqlalchemy"
            elif lang in ("typescript", "javascript"):
                # TypeScript interfaces/types handled separately via INTERFACE kind
                pass
            elif lang == "go":
                # Go structs with json/db tags are data models (struct_type captures)
                # All Go structs are potential data models; we mark them
                framework = "go_struct"
            elif lang == "java":
                for dec in decorators:
                    dec_name = dec.lstrip("@").split("(")[0].strip()
                    if dec_name in JAVA_DATA_ANNOTATIONS:
                        framework = "jpa"
                        break
            elif lang == "rust":
                for dec in decorators:
                    # Check for #[derive(Serialize, Deserialize, ...)]
                    if "derive" in dec:
                        for dm in RUST_DATA_DERIVES:
                            if dm in dec:
                                framework = "rust_serde"
                                break
                    if framework:
                        break
            elif lang == "ruby":
                for b in bases:
                    if b in RUBY_DATA_BASES or b == "ApplicationRecord":
                        framework = "active_record"
                        break

            if framework:
                fields: list[dict] = []
                if lang == "python":
                    fields = _extract_python_fields(
                        row["file_path"], row["name"], row["line_start"]
                    )
                self._store.upsert_data_model(row["id"], framework, fields)
                count += 1

        # Also mark INTERFACE symbols as data models
        for row in self._store.get_all_symbols():
            if row["kind"] == "interface":
                self._store.upsert_data_model(row["id"], "typescript_interface", [])
                count += 1

        return count
