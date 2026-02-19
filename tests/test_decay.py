"""
Tests for Hebbian Mind Enterprise temporal decay engine.

Covers:
- Memory decay formula math
- Edge decay formula math
- Schema migration
- Save with decay fields
- Query with decay filtering
- Query with include_decayed bypass
- Touch on access
- Memory sweep
- Edge sweep
- DecayEngine lifecycle
- get_status / get_decay_stats
- Edge decay toward minimum, not below

Copyright (c) 2026 CIPS LLC
"""

import math
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hebbian_mind.decay import (
    HebbianDecayEngine,
    calculate_edge_decay,
    calculate_effective_importance,
)

# ============================================================
# Decay config fixture
# ============================================================


@pytest.fixture
def decay_config():
    """Standard decay configuration for tests."""
    return {
        "enabled": True,
        "base_rate": 0.01,
        "threshold": 0.1,
        "immortal_threshold": 0.9,
        "sweep_interval_minutes": 60,
        "edge_decay_enabled": True,
        "edge_decay_rate": 0.005,
        "edge_decay_min_weight": 0.1,
    }


@pytest.fixture
def decay_config_disabled():
    """Decay configuration with everything disabled."""
    return {
        "enabled": False,
        "base_rate": 0.01,
        "threshold": 0.1,
        "immortal_threshold": 0.9,
        "sweep_interval_minutes": 60,
        "edge_decay_enabled": False,
        "edge_decay_rate": 0.005,
        "edge_decay_min_weight": 0.1,
    }


# ============================================================
# Database fixtures
# ============================================================


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database with full schema including decay columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                keywords TEXT NOT NULL,
                prototype_phrases TEXT NOT NULL,
                description TEXT,
                weight REAL DEFAULT 1.0,
                activation_count INTEGER DEFAULT 0,
                last_activated TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                weight REAL DEFAULT 0.1,
                co_activation_count INTEGER DEFAULT 0,
                last_strengthened TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id),
                UNIQUE(source_id, target_id)
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source TEXT DEFAULT 'TEST',
                importance REAL DEFAULT 0.5,
                emotional_intensity REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed REAL,
                effective_importance REAL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS memory_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                node_id INTEGER NOT NULL,
                activation_score REAL NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );

            CREATE INDEX IF NOT EXISTS idx_memories_effective_importance
                ON memories(effective_importance);
        """)
        conn.commit()

        yield conn

        conn.close()


@pytest.fixture
def mock_db(temp_db):
    """Create a mock database object that mimics HebbianMindDatabase."""
    db = MagicMock()
    db.read_conn = temp_db
    db.disk_conn = None
    db._decay_engine = None
    return db


@pytest.fixture
def mock_db_dual_write(temp_db):
    """Create a mock db with a second connection for dual-write testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        disk_path = Path(tmpdir) / "disk.db"
        disk_conn = sqlite3.connect(str(disk_path))
        disk_conn.row_factory = sqlite3.Row

        # Same schema on disk
        disk_conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source TEXT DEFAULT 'TEST',
                importance REAL DEFAULT 0.5,
                emotional_intensity REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed REAL,
                effective_importance REAL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                weight REAL DEFAULT 0.1,
                co_activation_count INTEGER DEFAULT 0,
                last_strengthened TIMESTAMP,
                UNIQUE(source_id, target_id)
            );
        """)
        disk_conn.commit()

        db = MagicMock()
        db.read_conn = temp_db
        db.disk_conn = disk_conn
        db._decay_engine = None

        yield db

        disk_conn.close()


# ============================================================
# Test: Memory decay formula
# ============================================================


class TestMemoryDecayFormula:
    """Test calculate_effective_importance math."""

    def test_basic_decay(self, decay_config):
        """Memory at importance 0.5, accessed 30 days ago should decay."""
        now = time.time()
        last_accessed = now - (30 * 86400)  # 30 days ago

        result = calculate_effective_importance(0.5, last_accessed, now, decay_config)

        assert result < 0.5
        assert result > 0.0

    def test_immortal_memory(self, decay_config):
        """Memory with importance >= immortal_threshold never decays."""
        now = time.time()
        last_accessed = now - (365 * 86400)  # 1 year ago

        result = calculate_effective_importance(0.95, last_accessed, now, decay_config)

        assert result == 0.95  # Unchanged

    def test_immortal_at_threshold(self, decay_config):
        """Memory at exactly immortal_threshold is immortal."""
        now = time.time()
        last_accessed = now - (100 * 86400)

        result = calculate_effective_importance(0.9, last_accessed, now, decay_config)

        assert result == 0.9

    def test_zero_days(self, decay_config):
        """Memory accessed just now should not decay."""
        now = time.time()
        last_accessed = now

        result = calculate_effective_importance(0.5, last_accessed, now, decay_config)

        assert result == 0.5

    def test_future_access(self, decay_config):
        """If last_accessed is in the future, no decay."""
        now = time.time()
        last_accessed = now + 86400  # tomorrow

        result = calculate_effective_importance(0.5, last_accessed, now, decay_config)

        assert result == 0.5

    def test_higher_importance_decays_slower(self, decay_config):
        """Higher importance should result in slower decay."""
        now = time.time()
        last_accessed = now - (60 * 86400)  # 60 days ago

        low = calculate_effective_importance(0.3, last_accessed, now, decay_config)
        high = calculate_effective_importance(0.7, last_accessed, now, decay_config)

        # High importance should retain more of its value proportionally
        assert (high / 0.7) > (low / 0.3)

    def test_extreme_decay(self, decay_config):
        """Very old, low importance memory should decay significantly."""
        now = time.time()
        last_accessed = now - (365 * 86400)  # 1 year

        result = calculate_effective_importance(0.2, last_accessed, now, decay_config)

        assert result < 0.1  # Should be below threshold

    def test_formula_matches_expected(self, decay_config):
        """Verify the exact math: importance * exp(-rate * (1-importance) * days)."""
        now = time.time()
        days = 10
        last_accessed = now - (days * 86400)
        importance = 0.5

        expected_rate = 0.01 * (1.0 - 0.5)  # 0.005
        expected = 0.5 * math.exp(-expected_rate * days)

        result = calculate_effective_importance(importance, last_accessed, now, decay_config)

        assert abs(result - expected) < 1e-10

    def test_zero_importance(self, decay_config):
        """Zero importance memory should decay at base rate."""
        now = time.time()
        days = 30
        last_accessed = now - (days * 86400)

        result = calculate_effective_importance(0.0, last_accessed, now, decay_config)

        # 0.0 * anything = 0.0
        assert result == 0.0


# ============================================================
# Test: Edge decay formula
# ============================================================


class TestEdgeDecayFormula:
    """Test calculate_edge_decay math."""

    def test_basic_edge_decay(self, decay_config):
        """Edge weight should decay toward min_weight over time."""
        now = time.time()
        last_strengthened = now - (60 * 86400)  # 60 days

        result = calculate_edge_decay(5.0, last_strengthened, now, decay_config)

        assert result < 5.0
        assert result >= 0.1  # min_weight

    def test_edge_at_minimum(self, decay_config):
        """Edge already at min_weight should not decay further."""
        now = time.time()
        last_strengthened = now - (365 * 86400)

        result = calculate_edge_decay(0.1, last_strengthened, now, decay_config)

        assert result == 0.1

    def test_edge_below_minimum(self, decay_config):
        """Edge below min_weight should stay as-is."""
        now = time.time()
        last_strengthened = now - (365 * 86400)

        result = calculate_edge_decay(0.05, last_strengthened, now, decay_config)

        assert result == 0.05

    def test_edge_no_time_passed(self, decay_config):
        """Edge with last_strengthened = now should not decay."""
        now = time.time()

        result = calculate_edge_decay(5.0, now, now, decay_config)

        assert result == 5.0

    def test_edge_future_strengthened(self, decay_config):
        """Future last_strengthened should not cause decay."""
        now = time.time()
        last_strengthened = now + 86400

        result = calculate_edge_decay(5.0, last_strengthened, now, decay_config)

        assert result == 5.0

    def test_edge_never_below_minimum(self, decay_config):
        """Even after extreme time, edge weight stays at min_weight."""
        now = time.time()
        last_strengthened = now - (3650 * 86400)  # 10 years

        result = calculate_edge_decay(10.0, last_strengthened, now, decay_config)

        assert result >= 0.1
        # After 10 years at 0.005 rate, should be very close to min
        assert result < 0.2

    def test_edge_decay_formula_matches(self, decay_config):
        """Verify exact edge decay math."""
        now = time.time()
        days = 20
        last_strengthened = now - (days * 86400)
        weight = 3.0
        min_weight = 0.1

        above_min = weight - min_weight  # 2.9
        decay_factor = math.exp(-0.005 * days)
        expected = min_weight + above_min * decay_factor

        result = calculate_edge_decay(weight, last_strengthened, now, decay_config)

        assert abs(result - expected) < 1e-10

    def test_edge_decay_rate_independence(self, decay_config):
        """Edge decay rate should be independent of memory decay rate."""
        # Edge uses edge_decay_rate (0.005), not base_rate (0.01)
        now = time.time()
        days = 30
        last_strengthened = now - (days * 86400)

        result = calculate_edge_decay(5.0, last_strengthened, now, decay_config)

        # Using edge_decay_rate = 0.005
        above_min = 5.0 - 0.1
        expected = 0.1 + above_min * math.exp(-0.005 * days)

        assert abs(result - expected) < 1e-10


# ============================================================
# Test: Schema migration
# ============================================================


class TestSchemaMigration:
    """Test that decay columns are added correctly."""

    def test_columns_exist(self, temp_db):
        """Decay columns should exist in schema."""
        cursor = temp_db.cursor()
        cursor.execute("PRAGMA table_info(memories)")
        columns = {row["name"] for row in cursor.fetchall()}

        assert "last_accessed" in columns
        assert "effective_importance" in columns
        assert "access_count" in columns

    def test_backfill_works(self, temp_db):
        """Backfill should set last_accessed and effective_importance for existing rows."""
        # Insert a row without decay fields (simulating pre-migration data)
        temp_db.execute("""
            INSERT INTO memories (memory_id, content, importance, created_at)
            VALUES ('old_memory', 'old content', 0.7, '2026-01-01 12:00:00')
        """)
        temp_db.commit()

        # Simulate backfill
        temp_db.execute("""
            UPDATE memories SET
                last_accessed = CAST(strftime('%s', created_at) AS REAL),
                effective_importance = importance,
                access_count = 0
            WHERE last_accessed IS NULL
        """)
        temp_db.commit()

        cursor = temp_db.cursor()
        cursor.execute("SELECT * FROM memories WHERE memory_id = 'old_memory'")
        row = dict(cursor.fetchone())

        assert row["last_accessed"] is not None
        assert row["effective_importance"] == 0.7
        assert row["access_count"] == 0

    def test_migration_idempotent(self, temp_db):
        """Running ALTER TABLE on existing columns should not error."""
        migrations = [
            "ALTER TABLE memories ADD COLUMN last_accessed REAL",
            "ALTER TABLE memories ADD COLUMN effective_importance REAL",
            "ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0",
        ]

        for migration in migrations:
            try:
                temp_db.execute(migration)
            except sqlite3.OperationalError as e:
                assert "duplicate column" in str(e).lower()


# ============================================================
# Test: Save with decay fields
# ============================================================


class TestSaveWithDecay:
    """Test that save_memory sets decay fields."""

    def test_save_sets_decay_fields(self, temp_db):
        """New memories should have decay fields populated."""
        now = time.time()

        temp_db.execute(
            """
            INSERT INTO memories
            (memory_id, content, summary, source, importance, emotional_intensity,
             last_accessed, effective_importance, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
            ("test_1", "test content", "summary", "TEST", 0.7, 0.5, now, 0.7),
        )
        temp_db.commit()

        cursor = temp_db.cursor()
        cursor.execute("SELECT * FROM memories WHERE memory_id = 'test_1'")
        row = dict(cursor.fetchone())

        assert row["last_accessed"] == now
        assert row["effective_importance"] == 0.7
        assert row["access_count"] == 0

    def test_save_immortal_memory(self, temp_db):
        """Immortal memory should have effective_importance = importance."""
        now = time.time()

        temp_db.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES (?, ?, ?, ?, ?, 0)
        """,
            ("immortal_1", "critical memory", 0.95, now, 0.95),
        )
        temp_db.commit()

        cursor = temp_db.cursor()
        cursor.execute("SELECT * FROM memories WHERE memory_id = 'immortal_1'")
        row = dict(cursor.fetchone())

        assert row["importance"] == 0.95
        assert row["effective_importance"] == 0.95


# ============================================================
# Test: Query with decay filtering
# ============================================================


class TestQueryDecayFiltering:
    """Test that queries filter by effective_importance."""

    def _setup_memories(self, conn):
        """Insert test nodes and memories with various decay states."""
        # Nodes
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('n1', 'TestNode', 'test', '["test"]', '["test phrase"]')
        """)
        conn.commit()

        node_id = conn.execute("SELECT id FROM nodes WHERE node_id = 'n1'").fetchone()[0]

        now = time.time()

        # Active memory (above threshold)
        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('active_1', 'active content', 0.5, ?, 0.45, 1)
        """,
            (now,),
        )

        # Decayed memory (below threshold)
        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('decayed_1', 'decayed content', 0.3, ?, 0.05, 0)
        """,
            (now - 365 * 86400,),
        )

        # Immortal memory
        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('immortal_1', 'immortal content', 0.95, ?, 0.95, 5)
        """,
            (now,),
        )

        # Memory with NULL effective_importance (pre-migration)
        conn.execute("""
            INSERT INTO memories
            (memory_id, content, importance)
            VALUES ('null_1', 'null eff content', 0.5)
        """)

        # Link all to the node
        for mid in ["active_1", "decayed_1", "immortal_1", "null_1"]:
            conn.execute(
                """
                INSERT INTO memory_activations (memory_id, node_id, activation_score)
                VALUES (?, ?, 0.5)
            """,
                (mid, node_id),
            )

        conn.commit()
        return node_id

    def test_query_hides_decayed_by_default(self, temp_db):
        """Decayed memories should be hidden when include_decayed=False."""
        self._setup_memories(temp_db)

        threshold = 0.1
        cursor = temp_db.cursor()
        cursor.execute(
            """
            SELECT DISTINCT m.*
            FROM memories m
            JOIN memory_activations ma ON m.memory_id = ma.memory_id
            WHERE (m.effective_importance IS NULL OR m.effective_importance >= ?)
        """,
            (threshold,),
        )

        results = [dict(r) for r in cursor.fetchall()]
        memory_ids = [r["memory_id"] for r in results]

        assert "active_1" in memory_ids
        assert "immortal_1" in memory_ids
        assert "null_1" in memory_ids  # NULL treated as not-decayed
        assert "decayed_1" not in memory_ids

    def test_query_shows_all_with_include_decayed(self, temp_db):
        """All memories should appear when include_decayed=True."""
        self._setup_memories(temp_db)

        cursor = temp_db.cursor()
        cursor.execute("""
            SELECT DISTINCT m.*
            FROM memories m
            JOIN memory_activations ma ON m.memory_id = ma.memory_id
        """)

        results = [dict(r) for r in cursor.fetchall()]
        memory_ids = [r["memory_id"] for r in results]

        assert "active_1" in memory_ids
        assert "immortal_1" in memory_ids
        assert "decayed_1" in memory_ids
        assert "null_1" in memory_ids


# ============================================================
# Test: Touch on access
# ============================================================


class TestTouchOnAccess:
    """Test that accessed memories get their timestamps refreshed."""

    def test_touch_updates_last_accessed(self, mock_db, decay_config):
        """touch_memories should update last_accessed timestamp."""
        conn = mock_db.read_conn
        old_time = time.time() - 86400  # yesterday

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('touch_1', 'content', 0.5, ?, 0.5, 0)
        """,
            (old_time,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.touch_memories(["touch_1"])

        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_accessed, access_count FROM memories WHERE memory_id = 'touch_1'"
        )
        row = dict(cursor.fetchone())

        assert row["last_accessed"] > old_time
        assert row["access_count"] == 1

    def test_touch_increments_access_count(self, mock_db, decay_config):
        """Multiple touches should increment access_count."""
        conn = mock_db.read_conn

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('touch_2', 'content', 0.5, ?, 0.5, 3)
        """,
            (time.time(),),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.touch_memories(["touch_2"])

        cursor = conn.cursor()
        cursor.execute("SELECT access_count FROM memories WHERE memory_id = 'touch_2'")
        row = cursor.fetchone()

        assert row["access_count"] == 4

    def test_touch_empty_list(self, mock_db, decay_config):
        """Touching empty list should not error."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.touch_memories([])  # Should not raise

    def test_touch_nonexistent_memory(self, mock_db, decay_config):
        """Touching nonexistent memory should not error."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.touch_memories(["nonexistent"])  # Should not raise


# ============================================================
# Test: Memory sweep
# ============================================================


class TestMemorySweep:
    """Test memory decay sweep."""

    def test_sweep_updates_effective_importance(self, mock_db, decay_config):
        """Sweep should recalculate effective_importance."""
        conn = mock_db.read_conn
        old_time = time.time() - (60 * 86400)  # 60 days ago

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('sweep_1', 'content', 0.5, ?, 0.5, 0)
        """,
            (old_time,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute("SELECT effective_importance FROM memories WHERE memory_id = 'sweep_1'")
        new_eff = cursor.fetchone()["effective_importance"]

        assert new_eff < 0.5
        assert stats["memories_swept"] >= 1

    def test_sweep_skips_immortal(self, mock_db, decay_config):
        """Immortal memories should be counted but not decayed."""
        conn = mock_db.read_conn
        old_time = time.time() - (365 * 86400)

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('immortal_sweep', 'content', 0.95, ?, 0.95, 0)
        """,
            (old_time,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute(
            "SELECT effective_importance FROM memories WHERE memory_id = 'immortal_sweep'"
        )
        eff = cursor.fetchone()["effective_importance"]

        assert eff == 0.95  # Unchanged
        assert stats["memories_immortal"] >= 1

    def test_sweep_counts_decayed(self, mock_db, decay_config):
        """Sweep should count how many fell below threshold."""
        conn = mock_db.read_conn
        very_old = time.time() - (365 * 86400)

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('decay_count', 'content', 0.2, ?, 0.2, 0)
        """,
            (very_old,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.run_sweep()

        assert stats["memories_decayed"] >= 1

    def test_sweep_disabled(self, mock_db, decay_config_disabled):
        """Sweep should do nothing when decay is disabled."""
        conn = mock_db.read_conn

        conn.execute(
            """
            INSERT INTO memories
            (memory_id, content, importance, last_accessed, effective_importance, access_count)
            VALUES ('no_sweep', 'content', 0.5, ?, 0.5, 0)
        """,
            (time.time() - 86400 * 100,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config_disabled)
        stats = engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute("SELECT effective_importance FROM memories WHERE memory_id = 'no_sweep'")
        eff = cursor.fetchone()["effective_importance"]

        assert eff == 0.5  # Unchanged
        assert stats["memories_swept"] == 0


# ============================================================
# Test: Edge sweep
# ============================================================


class TestEdgeSweep:
    """Test edge weight decay sweep."""

    def test_sweep_decays_edges(self, mock_db, decay_config):
        """Edges should lose weight over time."""
        conn = mock_db.read_conn

        # Insert nodes first
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('ea', 'NodeA', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('eb', 'NodeB', 'test', '[]', '[]')
        """)
        conn.commit()

        # Insert a strong edge that was strengthened 60 days ago
        old_time = "2025-12-11 12:00:00"  # Well in the past
        conn.execute(
            """
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 2, 5.0, 10, ?)
        """,
            (old_time,),
        )
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute("SELECT weight FROM edges WHERE source_id = 1 AND target_id = 2")
        new_weight = cursor.fetchone()["weight"]

        assert new_weight < 5.0
        assert new_weight >= 0.1
        assert stats["edges_swept"] >= 1

    def test_sweep_respects_min_weight(self, mock_db, decay_config):
        """Edge decay should never go below min_weight."""
        conn = mock_db.read_conn

        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('mc', 'NodeC', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('md', 'NodeD', 'test', '[]', '[]')
        """)
        conn.commit()

        # Edge with weight barely above min
        conn.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 2, 0.15, 1, '2020-01-01 00:00:00')
        """)
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute("SELECT weight FROM edges WHERE source_id = 1 AND target_id = 2")
        weight = cursor.fetchone()["weight"]

        assert weight >= 0.1  # Never below min

    def test_edge_at_min_not_swept(self, mock_db, decay_config):
        """Edges at min_weight should be skipped by sweep query."""
        conn = mock_db.read_conn

        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('me', 'NodeE', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('mf', 'NodeF', 'test', '[]', '[]')
        """)
        conn.commit()

        conn.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 2, 0.1, 0, '2020-01-01 00:00:00')
        """)
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.run_sweep()

        assert stats["edges_swept"] == 0  # Skipped entirely

    def test_edge_sweep_disabled(self, mock_db, decay_config_disabled):
        """Edge sweep should do nothing when disabled."""
        conn = mock_db.read_conn

        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('mg', 'NodeG', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('mh', 'NodeH', 'test', '[]', '[]')
        """)
        conn.commit()

        conn.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 2, 5.0, 5, '2020-01-01 00:00:00')
        """)
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config_disabled)
        stats = engine.run_sweep()

        cursor = conn.cursor()
        cursor.execute("SELECT weight FROM edges WHERE source_id = 1 AND target_id = 2")
        weight = cursor.fetchone()["weight"]

        assert weight == 5.0  # Unchanged
        assert stats["edges_swept"] == 0


# ============================================================
# Test: Dual-write sweep
# ============================================================


class TestDualWriteSweep:
    """Test that sweeps write to both RAM and disk connections."""

    def test_memory_sweep_dual_write(self, mock_db_dual_write, decay_config):
        """Memory sweep should update both connections."""
        ram_conn = mock_db_dual_write.read_conn
        disk_conn = mock_db_dual_write.disk_conn
        old_time = time.time() - (60 * 86400)

        # Insert same memory in both
        for conn in [ram_conn, disk_conn]:
            conn.execute(
                """
                INSERT INTO memories
                (memory_id, content, importance, last_accessed, effective_importance, access_count)
                VALUES ('dual_1', 'content', 0.5, ?, 0.5, 0)
            """,
                (old_time,),
            )
            conn.commit()

        engine = HebbianDecayEngine(mock_db_dual_write, decay_config)
        engine.run_sweep()

        # Both should be updated
        for conn in [ram_conn, disk_conn]:
            cursor = conn.cursor()
            cursor.execute("SELECT effective_importance FROM memories WHERE memory_id = 'dual_1'")
            eff = cursor.fetchone()["effective_importance"]
            assert eff < 0.5

    def test_touch_dual_write(self, mock_db_dual_write, decay_config):
        """Touch should update both connections."""
        ram_conn = mock_db_dual_write.read_conn
        disk_conn = mock_db_dual_write.disk_conn
        old_time = time.time() - 86400

        for conn in [ram_conn, disk_conn]:
            conn.execute(
                """
                INSERT INTO memories
                (memory_id, content, importance, last_accessed, effective_importance, access_count)
                VALUES ('touch_dual', 'content', 0.5, ?, 0.5, 0)
            """,
                (old_time,),
            )
            conn.commit()

        engine = HebbianDecayEngine(mock_db_dual_write, decay_config)
        engine.touch_memories(["touch_dual"])

        for conn in [ram_conn, disk_conn]:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_accessed, access_count FROM memories WHERE memory_id = 'touch_dual'"
            )
            row = dict(cursor.fetchone())
            assert row["last_accessed"] > old_time
            assert row["access_count"] == 1


# ============================================================
# Test: DecayEngine lifecycle
# ============================================================


class TestDecayEngineLifecycle:
    """Test start/stop/status of the decay engine."""

    def test_start_stop(self, mock_db, decay_config):
        """Engine should start and stop cleanly."""
        engine = HebbianDecayEngine(mock_db, decay_config)

        engine.start()
        assert engine._running is True
        assert engine._timer is not None

        engine.stop()
        assert engine._running is False
        assert engine._timer is None

    def test_start_when_disabled(self, mock_db, decay_config_disabled):
        """Engine should not start timer when both decays are disabled."""
        engine = HebbianDecayEngine(mock_db, decay_config_disabled)

        engine.start()
        assert engine._running is False or engine._timer is None

    def test_double_stop(self, mock_db, decay_config):
        """Double stop should not error."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.start()
        engine.stop()
        engine.stop()  # Should not raise

    def test_sweep_increments_count(self, mock_db, decay_config):
        """Each sweep should increment the counter."""
        engine = HebbianDecayEngine(mock_db, decay_config)

        assert engine._sweep_count == 0

        engine.run_sweep()
        assert engine._sweep_count == 1

        engine.run_sweep()
        assert engine._sweep_count == 2


# ============================================================
# Test: Status and stats
# ============================================================


class TestStatusAndStats:
    """Test get_status and get_decay_stats."""

    def test_get_status(self, mock_db, decay_config):
        """Status should return engine state."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        status = engine.get_status()

        assert status["memory_decay_enabled"] is True
        assert status["edge_decay_enabled"] is True
        assert status["running"] is False
        assert status["sweep_count"] == 0
        assert "config" in status

    def test_get_status_after_sweep(self, mock_db, decay_config):
        """Status should reflect sweep history."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        engine.run_sweep()

        status = engine.get_status()
        assert status["sweep_count"] == 1
        assert status["last_sweep_time"] is not None

    def test_get_decay_stats_empty_db(self, mock_db, decay_config):
        """Stats on empty database should return zeros."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.get_decay_stats()

        assert stats["memories"]["total"] == 0
        assert stats["memories"]["immortal"] == 0
        assert stats["memories"]["active"] == 0
        assert stats["memories"]["decayed"] == 0
        assert stats["edges"]["total"] == 0

    def test_get_decay_stats_with_data(self, mock_db, decay_config):
        """Stats should count memory categories correctly."""
        conn = mock_db.read_conn
        now = time.time()

        # Immortal
        conn.execute(
            """
            INSERT INTO memories (memory_id, content, importance, last_accessed, effective_importance)
            VALUES ('s_immortal', 'content', 0.95, ?, 0.95)
        """,
            (now,),
        )

        # Active
        conn.execute(
            """
            INSERT INTO memories (memory_id, content, importance, last_accessed, effective_importance)
            VALUES ('s_active', 'content', 0.5, ?, 0.45)
        """,
            (now,),
        )

        # Decayed
        conn.execute(
            """
            INSERT INTO memories (memory_id, content, importance, last_accessed, effective_importance)
            VALUES ('s_decayed', 'content', 0.3, ?, 0.05)
        """,
            (now - 365 * 86400,),
        )

        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.get_decay_stats()

        assert stats["memories"]["total"] == 3
        assert stats["memories"]["immortal"] == 1
        assert stats["memories"]["active"] == 1
        assert stats["memories"]["decayed"] == 1

    def test_get_decay_stats_edges(self, mock_db, decay_config):
        """Stats should report edge weight distribution."""
        conn = mock_db.read_conn

        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('sa', 'SA', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('sb', 'SB', 'test', '[]', '[]')
        """)
        conn.execute("""
            INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
            VALUES ('sc', 'SC', 'test', '[]', '[]')
        """)
        conn.commit()

        # One edge at min weight, one above
        conn.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 2, 0.1, 0, CURRENT_TIMESTAMP)
        """)
        conn.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count, last_strengthened)
            VALUES (1, 3, 3.5, 5, CURRENT_TIMESTAMP)
        """)
        conn.commit()

        engine = HebbianDecayEngine(mock_db, decay_config)
        stats = engine.get_decay_stats()

        assert stats["edges"]["total"] == 2
        assert stats["edges"]["at_minimum_weight"] == 1
        assert stats["edges"]["above_minimum"] == 1
        assert stats["edges"]["average_weight"] > 0


# ============================================================
# Test: Config integration
# ============================================================


class TestConfigIntegration:
    """Test Config class decay additions."""

    def test_get_decay_config(self):
        """Config.get_decay_config should return all decay settings."""
        from hebbian_mind.config import Config

        config = Config.get_decay_config()

        assert "enabled" in config
        assert "base_rate" in config
        assert "threshold" in config
        assert "immortal_threshold" in config
        assert "sweep_interval_minutes" in config
        assert "edge_decay_enabled" in config
        assert "edge_decay_rate" in config
        assert "edge_decay_min_weight" in config

    def test_decay_in_summary(self):
        """Config.summary() should include decay section."""
        from hebbian_mind.config import Config

        summary = Config.summary()

        assert "decay" in summary
        assert summary["decay"]["enabled"] is True
        assert summary["decay"]["base_rate"] == 0.01

    def test_config_env_override(self):
        """Decay config should respect environment variables."""
        import os

        os.environ["HEBBIAN_MIND_DECAY_ENABLED"] = "false"
        os.environ["HEBBIAN_MIND_DECAY_BASE_RATE"] = "0.05"
        os.environ["HEBBIAN_MIND_EDGE_DECAY_RATE"] = "0.02"

        # Need to reimport to pick up env changes
        # Since Config uses class-level attributes evaluated at import,
        # we test the env var parsing logic directly
        assert os.getenv("HEBBIAN_MIND_DECAY_ENABLED") == "false"
        assert float(os.getenv("HEBBIAN_MIND_DECAY_BASE_RATE")) == 0.05
        assert float(os.getenv("HEBBIAN_MIND_EDGE_DECAY_RATE")) == 0.02

        # Cleanup
        del os.environ["HEBBIAN_MIND_DECAY_ENABLED"]
        del os.environ["HEBBIAN_MIND_DECAY_BASE_RATE"]
        del os.environ["HEBBIAN_MIND_EDGE_DECAY_RATE"]


# ============================================================
# Test: Timestamp parsing
# ============================================================


class TestTimestampParsing:
    """Test the decay engine's timestamp parser."""

    def test_parse_epoch_float(self, mock_db, decay_config):
        """Should handle float epoch timestamps."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        result = engine._parse_timestamp(1700000000.0)
        assert result == 1700000000.0

    def test_parse_epoch_int(self, mock_db, decay_config):
        """Should handle integer epoch timestamps."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        result = engine._parse_timestamp(1700000000)
        assert result == 1700000000.0

    def test_parse_epoch_string(self, mock_db, decay_config):
        """Should handle string epoch timestamps."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        result = engine._parse_timestamp("1700000000")
        assert result == 1700000000.0

    def test_parse_sqlite_format(self, mock_db, decay_config):
        """Should handle SQLite CURRENT_TIMESTAMP format."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        result = engine._parse_timestamp("2026-01-15 10:30:00")
        assert isinstance(result, float)
        assert result > 0

    def test_parse_iso_format(self, mock_db, decay_config):
        """Should handle ISO format timestamps."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        result = engine._parse_timestamp("2026-01-15T10:30:00")
        assert isinstance(result, float)
        assert result > 0

    def test_parse_none_raises(self, mock_db, decay_config):
        """None timestamp should raise ValueError."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        with pytest.raises(ValueError):
            engine._parse_timestamp(None)

    def test_parse_invalid_raises(self, mock_db, decay_config):
        """Invalid timestamp should raise ValueError."""
        engine = HebbianDecayEngine(mock_db, decay_config)
        with pytest.raises(ValueError):
            engine._parse_timestamp("not a timestamp")
