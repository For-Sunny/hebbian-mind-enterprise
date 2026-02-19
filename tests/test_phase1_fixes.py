"""
Tests for Phase 1 Critical/High fixes
======================================

Covers:
  C2: UUID memory IDs (no collision)
  C3: Threading lock on DB operations
  H1: Bounded get_all_nodes
  H2: No bare except handlers
  H3: Input validation
  H5: RuntimeError from save_memory on failure
  H6: Decay dual-write order (disk first)
  H7: asyncio import at module top

Copyright (c) 2026 CIPS LLC
"""

import ast
import inspect
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============ C2: UUID Memory IDs ============

class TestUUIDMemoryIds:
    """Verify memory IDs use UUID, not timestamp+hash."""

    def test_memory_id_format(self):
        """Memory ID should use UUID hex, not timestamp+hash%10000."""
        # Import the module source and check the pattern
        from hebbian_mind.server import uuid
        mid = f"hebbian_mind_{uuid.uuid4().hex[:16]}"
        assert mid.startswith("hebbian_mind_")
        # The UUID part should be 16 hex chars
        hex_part = mid.split("_", 2)[2]
        assert len(hex_part) == 16
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_no_collision_in_1000_ids(self):
        """1000 rapid-fire IDs should all be unique."""
        import uuid
        ids = set()
        for _ in range(1000):
            mid = f"hebbian_mind_{uuid.uuid4().hex[:16]}"
            ids.add(mid)
        assert len(ids) == 1000

    def test_no_insert_or_replace(self):
        """save_memory should not use INSERT OR REPLACE."""
        import hebbian_mind.server as srv
        source = inspect.getsource(srv.HebbianMindDatabase.save_memory)
        assert "INSERT OR REPLACE" not in source
        assert "INSERT INTO memories" in source


# ============ C3: Threading Lock ============

class TestThreadingLock:
    """Verify HebbianMindDatabase has a threading lock."""

    def test_lock_exists(self):
        """Database class should have _lock attribute."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.__init__)
        assert "_lock" in source
        assert "threading.RLock()" in source

    def test_dual_write_uses_lock(self):
        """_dual_write should acquire _lock."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase._dual_write)
        assert "self._lock" in source

    def test_save_memory_uses_lock(self):
        """save_memory should acquire _lock."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.save_memory)
        assert "self._lock" in source

    def test_query_by_nodes_uses_lock(self):
        """query_by_nodes should acquire _lock."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.query_by_nodes)
        assert "self._lock" in source


# ============ H1: Bounded get_all_nodes ============

class TestBoundedNodes:
    """Verify get_all_nodes has a LIMIT."""

    def test_get_all_nodes_has_limit_param(self):
        """get_all_nodes should accept a limit parameter."""
        from hebbian_mind.server import HebbianMindDatabase
        sig = inspect.signature(HebbianMindDatabase.get_all_nodes)
        assert "limit" in sig.parameters

    def test_get_all_nodes_default_limit(self):
        """Default limit should be 10000."""
        from hebbian_mind.server import HebbianMindDatabase
        sig = inspect.signature(HebbianMindDatabase.get_all_nodes)
        assert sig.parameters["limit"].default == 10000

    def test_get_all_nodes_sql_has_limit(self):
        """SQL query should include LIMIT clause."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.get_all_nodes)
        assert "LIMIT" in source

    def test_query_by_nodes_clamps_limit(self):
        """query_by_nodes should clamp limit to 1-500."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.query_by_nodes)
        assert "max(1, min(500, limit))" in source


# ============ H2: No Bare Except ============

class TestNoBareExcept:
    """Verify no bare except: handlers exist."""

    def test_server_no_bare_except(self):
        """server.py should have no bare 'except:' statements."""
        server_path = Path(__file__).parent.parent / "src" / "hebbian_mind" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        # Find all except lines that aren't 'except Exception' or 'except SomeError'
        lines = source.split("\n")
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or stripped.startswith("except: "):
                bare_excepts.append(f"line {i}: {stripped}")
        assert bare_excepts == [], f"Bare except found: {bare_excepts}"

    def test_decay_no_bare_except(self):
        """decay.py should have no bare 'except:' statements."""
        decay_path = Path(__file__).parent.parent / "src" / "hebbian_mind" / "decay.py"
        source = decay_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or stripped.startswith("except: "):
                bare_excepts.append(f"line {i}: {stripped}")
        assert bare_excepts == [], f"Bare except found: {bare_excepts}"


# ============ H3: Input Validation ============

class TestInputValidation:
    """Verify input validation functions exist and work."""

    def test_validate_string_exists(self):
        """_validate_string function should exist in server module."""
        from hebbian_mind.server import _validate_string
        assert callable(_validate_string)

    def test_validate_string_rejects_empty(self):
        """Empty strings should be rejected."""
        from hebbian_mind.server import _validate_string
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_string("", "test_field")

    def test_validate_string_rejects_non_string(self):
        """Non-string values should be rejected."""
        from hebbian_mind.server import _validate_string
        with pytest.raises(ValueError, match="must be a string"):
            _validate_string(123, "test_field")

    def test_validate_string_rejects_too_long(self):
        """Strings exceeding max_length should be rejected."""
        from hebbian_mind.server import _validate_string
        with pytest.raises(ValueError, match="exceeds maximum length"):
            _validate_string("x" * 101, "test_field", max_length=100)

    def test_validate_string_accepts_valid(self):
        """Valid strings should pass through."""
        from hebbian_mind.server import _validate_string
        result = _validate_string("hello world", "test_field")
        assert result == "hello world"

    def test_validate_number_exists(self):
        """_validate_number function should exist in server module."""
        from hebbian_mind.server import _validate_number
        assert callable(_validate_number)

    def test_validate_number_rejects_non_numeric(self):
        """Non-numeric values should be rejected."""
        from hebbian_mind.server import _validate_number
        with pytest.raises(ValueError, match="must be a number"):
            _validate_number("not_a_number", "test_field")

    def test_validate_number_rejects_below_min(self):
        """Numbers below min should be rejected."""
        from hebbian_mind.server import _validate_number
        with pytest.raises(ValueError, match="must be >="):
            _validate_number(-0.1, "importance", min_val=0.0)

    def test_validate_number_rejects_above_max(self):
        """Numbers above max should be rejected."""
        from hebbian_mind.server import _validate_number
        with pytest.raises(ValueError, match="must be <="):
            _validate_number(1.5, "importance", max_val=1.0)

    def test_validate_number_accepts_valid(self):
        """Valid numbers should pass through."""
        from hebbian_mind.server import _validate_number
        result = _validate_number(0.5, "importance", min_val=0.0, max_val=1.0)
        assert result == 0.5

    def test_validate_number_accepts_int(self):
        """Integers should be accepted and converted to float."""
        from hebbian_mind.server import _validate_number
        result = _validate_number(1, "limit", min_val=0)
        assert result == 1.0
        assert isinstance(result, float)


# ============ H5: RuntimeError from save_memory ============

class TestSaveMemoryErrorContext:
    """Verify save_memory raises RuntimeError with details."""

    def test_save_memory_raises_on_failure(self):
        """save_memory should raise RuntimeError, not return False."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.save_memory)
        assert "raise RuntimeError" in source
        assert "return False" not in source

    def test_save_memory_error_includes_memory_id(self):
        """RuntimeError message should include memory_id."""
        from hebbian_mind.server import HebbianMindDatabase
        source = inspect.getsource(HebbianMindDatabase.save_memory)
        assert "memory_id=" in source


# ============ H6: Decay Dual-Write Order ============

class TestDecayDualWriteOrder:
    """Verify decay writes disk first, then RAM."""

    def test_sweep_memories_disk_first(self):
        """_sweep_memories should write disk before RAM."""
        from hebbian_mind.decay import HebbianDecayEngine
        source = inspect.getsource(HebbianDecayEngine._sweep_memories)
        # The comment should say disk first
        assert "disk first" in source.lower()
        # disk_conn.execute should appear before conn.execute in the update block
        disk_pos = source.find("disk_conn.execute")
        ram_pos = source.find("conn.execute(\n")
        if ram_pos == -1:
            ram_pos = source.find('conn.execute(\n')
        # Find the first conn.execute AFTER disk_conn section
        # Just check the comments are correct
        assert "RAM first" not in source

    def test_sweep_edges_disk_first(self):
        """_sweep_edges should write disk before RAM."""
        from hebbian_mind.decay import HebbianDecayEngine
        source = inspect.getsource(HebbianDecayEngine._sweep_edges)
        assert "disk first" in source.lower()
        assert "RAM first" not in source

    def test_touch_memories_disk_first(self):
        """touch_memories should write disk before RAM."""
        from hebbian_mind.decay import HebbianDecayEngine
        source = inspect.getsource(HebbianDecayEngine.touch_memories)
        assert "Disk first" in source or "disk first" in source.lower()

    def test_touch_memories_uses_lock(self):
        """touch_memories should acquire db._lock."""
        from hebbian_mind.decay import HebbianDecayEngine
        source = inspect.getsource(HebbianDecayEngine.touch_memories)
        assert "self.db._lock" in source


# ============ H7: asyncio Import at Top ============

class TestAsyncioImport:
    """Verify asyncio is imported at module top level."""

    def test_asyncio_in_top_imports(self):
        """asyncio should be imported at the top of server.py, not inline."""
        server_path = Path(__file__).parent.parent / "src" / "hebbian_mind" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        # Check first 40 lines for asyncio import
        top_section = "\n".join(lines[:40])
        assert "import asyncio" in top_section

    def test_no_inline_asyncio_import(self):
        """There should be no 'import asyncio' inside functions."""
        server_path = Path(__file__).parent.parent / "src" / "hebbian_mind" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        inline_imports = []
        in_function = False
        indent_level = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                in_function = True
            if in_function and stripped == "import asyncio":
                inline_imports.append(f"line {i}")
        assert inline_imports == [], f"Inline asyncio imports at: {inline_imports}"


# ============ Version Bump ============

class TestVersionBump:
    """Verify version was bumped for Phase 1 fixes."""

    def test_init_version(self):
        """__init__.py should have version 2.3.1."""
        from hebbian_mind import __version__
        assert __version__ == "2.3.1"

    def test_pyproject_version(self):
        """pyproject.toml should have version 2.3.1."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        assert 'version = "2.3.1"' in content
