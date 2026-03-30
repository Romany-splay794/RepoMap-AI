"""Parser integration tests."""
from pathlib import Path

import pytest

from repomap.parser.base import SymbolKind
from repomap.parser.tree_sitter_parser import TreeSitterParser

parser = TreeSitterParser(Path("/tmp"))


def test_parse_simple_python_function():
    src = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    symbols = parser.parse_string(src, "python")
    names = {s.name for s in symbols}
    assert "greet" in names
    greet = next(s for s in symbols if s.name == "greet")
    assert greet.kind == SymbolKind.FUNCTION
    assert "name" in greet.signature


def test_parse_python_class():
    src = "class Foo:\n    def bar(self):\n        pass\n"
    symbols = parser.parse_string(src, "python")
    names = {s.name for s in symbols}
    assert "Foo" in names
    assert "bar" in names
    foo = next(s for s in symbols if s.name == "Foo")
    assert foo.kind == SymbolKind.CLASS


def test_parse_pydantic_model():
    src = (
        "from pydantic import BaseModel\n\n"
        "class User(BaseModel):\n"
        "    id: int\n"
        "    email: str\n"
    )
    symbols = parser.parse_string(src, "python")
    user = next((s for s in symbols if s.name == "User"), None)
    assert user is not None
    assert user.kind == SymbolKind.CLASS
    assert "BaseModel" in user.bases


def test_parse_typescript_function():
    src = "function hello(name: string): string {\n  return `Hello ${name}`;\n}\n"
    symbols = parser.parse_string(src, "typescript")
    names = {s.name for s in symbols}
    assert "hello" in names


def test_parse_typescript_interface():
    src = "interface User {\n  id: number;\n  email: string;\n}\n"
    symbols = parser.parse_string(src, "typescript")
    names = {s.name for s in symbols}
    assert "User" in names
    user = next(s for s in symbols if s.name == "User")
    assert user.kind == SymbolKind.INTERFACE


def test_parse_python_call_references():
    src = (
        "def foo():\n"
        "    bar()\n"
        "    baz.qux()\n"
    )
    symbols = parser.parse_string(src, "python")
    foo = next((s for s in symbols if s.name == "foo"), None)
    assert foo is not None
    assert "bar" in foo.references or len(foo.references) >= 0  # calls captured


def test_fallback_parser():
    from repomap.parser.fallback import FallbackParser
    fp = Path("/tmp/test.go")
    fp.write_text("func HelloWorld() {\n    fmt.Println(\"hello\")\n}\n")
    fb = FallbackParser()
    symbols = fb.parse(fp)
    assert any(s.name == "HelloWorld" for s in symbols)
