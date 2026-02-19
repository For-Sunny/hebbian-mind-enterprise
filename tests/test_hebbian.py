"""
Tests for Hebbian learning: co-activation strengthening

"Neurons that fire together, wire together"

Copyright (c) 2026 CIPS LLC
"""

import json
import sqlite3

import pytest


class TestNodeActivation:
    """Test node activation and keyword matching."""

    def test_keyword_exact_match(self, populated_db: sqlite3.Connection):
        """Test exact keyword match in content."""
        cursor = populated_db.cursor()
        content = "This is a test of the system"

        # Get node with 'test' keyword
        cursor.execute("SELECT * FROM nodes WHERE node_id = ?", ("node_1",))
        node = cursor.fetchone()
        keywords = json.loads(node["keywords"])

        # Check if any keyword matches
        content_lower = content.lower()
        matches = [kw for kw in keywords if kw.lower() in content_lower]

        assert "test" in matches

    def test_keyword_word_boundary_match(self, populated_db: sqlite3.Connection):
        """Test word boundary matching for keywords."""
        import re

        content = "testing is important"  # Contains 'test' but not as word boundary

        keyword = "test"
        content_lower = content.lower()

        # Exact substring match (should match)
        assert keyword in content_lower

        # Word boundary match (should NOT match 'test' in 'testing')
        word_boundary_match = bool(re.search(r"\b" + re.escape(keyword) + r"\b", content_lower))
        assert not word_boundary_match

    def test_prototype_phrase_matching(self, populated_db: sqlite3.Connection):
        """Test prototype phrase matching in content."""
        cursor = populated_db.cursor()
        content = "This is a test of the prototype system"

        cursor.execute("SELECT * FROM nodes WHERE node_id = ?", ("node_1",))
        node = cursor.fetchone()
        phrases = json.loads(node["prototype_phrases"])

        # Check if any phrase matches
        content_lower = content.lower()
        matches = [phrase for phrase in phrases if phrase.lower() in content_lower]

        assert "this is a test" in matches

    def test_activation_score_calculation(self, populated_db: sqlite3.Connection):
        """Test calculating activation scores based on matches."""

        # Simulate scoring logic
        score = 0.0

        # Keywords: test (0.25), example (0.25), sample (0.25)
        keywords_found = ["test", "example", "sample"]
        for _ in keywords_found:
            score += 0.25

        # Prototype phrase: "this is a test" (0.35)
        phrase_found = True
        if phrase_found:
            score += 0.35

        # Cap at 1.0
        score = min(score, 1.0)

        assert score == 1.0  # 3*0.25 + 0.35 = 1.10, capped at 1.0

    def test_activation_threshold_filtering(self, populated_db: sqlite3.Connection):
        """Test filtering activations by threshold."""
        activations = [
            {"node_id": 1, "score": 0.45},
            {"node_id": 2, "score": 0.25},
            {"node_id": 3, "score": 0.65},
        ]

        threshold = 0.3
        filtered = [a for a in activations if a["score"] >= threshold]

        assert len(filtered) == 2
        assert all(a["score"] >= threshold for a in filtered)

    def test_activation_count_increment(self, populated_db: sqlite3.Connection):
        """Test incrementing node activation count."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id, activation_count FROM nodes WHERE node_id = ?", ("node_1",))
        node = cursor.fetchone()
        node_id = node["id"]
        initial_count = node["activation_count"]

        # Increment activation count
        populated_db.execute(
            """
            UPDATE nodes SET
                activation_count = activation_count + 1,
                last_activated = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (node_id,),
        )
        populated_db.commit()

        # Verify increment
        cursor.execute(
            "SELECT activation_count, last_activated FROM nodes WHERE id = ?", (node_id,)
        )
        updated = cursor.fetchone()

        assert updated["activation_count"] == initial_count + 1
        assert updated["last_activated"] is not None

    def test_most_active_nodes_query(self, populated_db: sqlite3.Connection):
        """Test querying most activated nodes."""
        cursor = populated_db.cursor()

        # Set different activation counts
        cursor.execute("SELECT id FROM nodes")
        node_ids = [row["id"] for row in cursor.fetchall()]

        for i, node_id in enumerate(node_ids):
            populated_db.execute(
                """
                UPDATE nodes SET activation_count = ? WHERE id = ?
            """,
                (i * 10, node_id),
            )

        populated_db.commit()

        # Query most active
        cursor.execute("""
            SELECT name, activation_count
            FROM nodes
            ORDER BY activation_count DESC
            LIMIT 1
        """)
        most_active = cursor.fetchone()

        assert most_active["activation_count"] == 20  # Last node: 2 * 10


class TestHebbianStrengthening:
    """Test Hebbian edge strengthening through co-activation."""

    def test_edge_creation_on_co_activation(self, populated_db: sqlite3.Connection):
        """Test creating edge when nodes co-activate for first time."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_2",))
        node2_id = cursor.fetchone()["id"]

        # Ensure consistent ordering
        source_id = min(node1_id, node2_id)
        target_id = max(node1_id, node2_id)

        # Check no edge exists
        cursor.execute(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        )
        assert cursor.fetchone() is None

        # Create edge on first co-activation
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight, co_activation_count)
            VALUES (?, ?, ?, ?)
        """,
            (source_id, target_id, 0.15, 1),
        )
        populated_db.commit()

        # Verify edge created
        cursor.execute(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        )
        edge = cursor.fetchone()

        assert edge is not None
        assert edge["weight"] == 0.15
        assert edge["co_activation_count"] == 1

    def test_hebbian_strengthening_formula(self):
        """Test Hebbian strengthening calculation: weight += 1 / (1 + current_weight)."""
        current_weight = 0.15
        strengthening = 1 / (1 + current_weight)
        new_weight = current_weight + strengthening

        assert new_weight == pytest.approx(1.0196, rel=1e-4)

        # Test with higher weight (diminishing returns)
        current_weight = 5.0
        strengthening = 1 / (1 + current_weight)
        new_weight = current_weight + strengthening

        assert new_weight == pytest.approx(5.1667, rel=1e-4)

    def test_edge_strengthening_with_cap(self, populated_db: sqlite3.Connection):
        """Test edge strengthening with max weight cap."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes LIMIT 2")
        node_ids = [row["id"] for row in cursor.fetchall()]
        source_id, target_id = min(node_ids), max(node_ids)

        # Create edge with high weight
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight, co_activation_count)
            VALUES (?, ?, ?, ?)
        """,
            (source_id, target_id, 9.5, 10),
        )
        populated_db.commit()

        # Strengthen edge
        cursor.execute(
            "SELECT weight FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        )
        current = cursor.fetchone()["weight"]

        strengthening = 1 / (1 + current)
        new_weight = min(current + strengthening, 10.0)

        populated_db.execute(
            """
            UPDATE edges SET
                weight = ?,
                co_activation_count = co_activation_count + 1,
                last_strengthened = CURRENT_TIMESTAMP
            WHERE source_id = ? AND target_id = ?
        """,
            (new_weight, source_id, target_id),
        )
        populated_db.commit()

        # Verify weight is capped at 10.0
        cursor.execute(
            "SELECT weight FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        )
        final_weight = cursor.fetchone()["weight"]

        assert final_weight <= 10.0

    def test_co_activation_count_increment(self, populated_db: sqlite3.Connection):
        """Test incrementing co-activation count on strengthening."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes LIMIT 2")
        node_ids = [row["id"] for row in cursor.fetchall()]
        source_id, target_id = min(node_ids), max(node_ids)

        # Create edge
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight, co_activation_count)
            VALUES (?, ?, ?, ?)
        """,
            (source_id, target_id, 0.5, 1),
        )
        populated_db.commit()

        # Strengthen (simulate co-activation)
        cursor.execute(
            "SELECT weight, co_activation_count FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        )
        edge = cursor.fetchone()
        current_weight = edge["weight"]
        current_count = edge["co_activation_count"]

        new_weight = current_weight + (1 / (1 + current_weight))

        populated_db.execute(
            """
            UPDATE edges SET
                weight = ?,
                co_activation_count = co_activation_count + 1,
                last_strengthened = CURRENT_TIMESTAMP
            WHERE source_id = ? AND target_id = ?
        """,
            (new_weight, source_id, target_id),
        )
        populated_db.commit()

        # Verify count incremented
        cursor.execute(
            "SELECT co_activation_count FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        )
        new_count = cursor.fetchone()["co_activation_count"]

        assert new_count == current_count + 1

    def test_pairwise_strengthening(self, populated_db: sqlite3.Connection):
        """Test strengthening all edges between a set of co-activated nodes."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes LIMIT 3")
        node_ids = [row["id"] for row in cursor.fetchall()]

        # Simulate 3 nodes activating together - should create 3 edges
        # (1,2), (1,3), (2,3)
        pairs = []
        for i, id1 in enumerate(node_ids):
            for id2 in node_ids[i + 1 :]:
                source_id = min(id1, id2)
                target_id = max(id1, id2)
                pairs.append((source_id, target_id))

                # Create or strengthen edge
                populated_db.execute(
                    """
                    INSERT INTO edges (source_id, target_id, weight, co_activation_count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_id, target_id) DO UPDATE SET
                        weight = weight + (1.0 / (1.0 + weight)),
                        co_activation_count = co_activation_count + 1
                """,
                    (source_id, target_id, 0.15, 1),
                )

        populated_db.commit()

        # Verify all pairs have edges
        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]

        assert edge_count == 3  # 3 choose 2 = 3 pairs

    def test_strongest_connections_query(self, populated_db: sqlite3.Connection):
        """Test querying strongest connections."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes LIMIT 3")
        node_ids = [row["id"] for row in cursor.fetchall()]

        # Create edges with different weights
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """,
            (node_ids[0], node_ids[1], 0.3),
        )
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """,
            (node_ids[1], node_ids[2], 0.9),
        )
        populated_db.commit()

        # Query strongest
        cursor.execute("""
            SELECT n1.name as source, n2.name as target, e.weight
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
            ORDER BY e.weight DESC
            LIMIT 1
        """)
        strongest = cursor.fetchone()

        assert strongest["weight"] == 0.9

    def test_timestamp_update_on_strengthening(self, populated_db: sqlite3.Connection):
        """Test that last_strengthened timestamp updates."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes LIMIT 2")
        node_ids = [row["id"] for row in cursor.fetchall()]
        source_id, target_id = min(node_ids), max(node_ids)

        # Create edge
        populated_db.execute(
            """
            INSERT INTO edges (source_id, target_id, weight, last_strengthened)
            VALUES (?, ?, ?, ?)
        """,
            (source_id, target_id, 0.5, "2020-01-01 00:00:00"),
        )
        populated_db.commit()

        # Strengthen edge
        populated_db.execute(
            """
            UPDATE edges SET
                weight = weight + 0.1,
                last_strengthened = CURRENT_TIMESTAMP
            WHERE source_id = ? AND target_id = ?
        """,
            (source_id, target_id),
        )
        populated_db.commit()

        # Verify timestamp updated
        cursor.execute(
            "SELECT last_strengthened FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        )
        timestamp = cursor.fetchone()["last_strengthened"]

        assert timestamp != "2020-01-01 00:00:00"


class TestMemoryActivations:
    """Test tracking which nodes were activated by which memories."""

    def test_memory_activation_recording(self, populated_db: sqlite3.Connection):
        """Test recording node activations for a memory."""
        cursor = populated_db.cursor()

        # Create a test memory
        memory_id = "test_memory_001"
        populated_db.execute(
            """
            INSERT INTO memories (memory_id, content, summary, source)
            VALUES (?, ?, ?, ?)
        """,
            (memory_id, "Test content", "Test summary", "TEST"),
        )
        populated_db.commit()

        # Record activations
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node_id = cursor.fetchone()["id"]

        populated_db.execute(
            """
            INSERT INTO memory_activations (memory_id, node_id, activation_score)
            VALUES (?, ?, ?)
        """,
            (memory_id, node_id, 0.75),
        )
        populated_db.commit()

        # Verify activation recorded
        cursor.execute(
            """
            SELECT * FROM memory_activations
            WHERE memory_id = ? AND node_id = ?
        """,
            (memory_id, node_id),
        )
        activation = cursor.fetchone()

        assert activation is not None
        assert activation["activation_score"] == 0.75

    def test_query_memories_by_node(self, populated_db: sqlite3.Connection):
        """Test querying memories that activated a specific node."""
        cursor = populated_db.cursor()

        # Create memories
        memory_ids = ["mem_001", "mem_002"]
        for mem_id in memory_ids:
            populated_db.execute(
                """
                INSERT INTO memories (memory_id, content, summary)
                VALUES (?, ?, ?)
            """,
                (mem_id, f"Content {mem_id}", f"Summary {mem_id}"),
            )

        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node_id = cursor.fetchone()["id"]

        # Record activations
        for mem_id in memory_ids:
            populated_db.execute(
                """
                INSERT INTO memory_activations (memory_id, node_id, activation_score)
                VALUES (?, ?, ?)
            """,
                (mem_id, node_id, 0.5),
            )

        populated_db.commit()

        # Query memories by node
        cursor.execute(
            """
            SELECT DISTINCT m.*
            FROM memories m
            JOIN memory_activations ma ON m.memory_id = ma.memory_id
            WHERE ma.node_id = ?
        """,
            (node_id,),
        )

        memories = cursor.fetchall()
        assert len(memories) == 2

    def test_activation_score_aggregation(self, populated_db: sqlite3.Connection):
        """Test aggregating activation scores for memories."""
        cursor = populated_db.cursor()

        # Create memory
        memory_id = "mem_001"
        populated_db.execute(
            """
            INSERT INTO memories (memory_id, content, summary)
            VALUES (?, ?, ?)
        """,
            (memory_id, "Test content", "Summary"),
        )

        # Record multiple node activations
        cursor.execute("SELECT id FROM nodes")
        node_ids = [row["id"] for row in cursor.fetchall()]

        scores = [0.5, 0.7, 0.3]
        for node_id, score in zip(node_ids, scores):
            populated_db.execute(
                """
                INSERT INTO memory_activations (memory_id, node_id, activation_score)
                VALUES (?, ?, ?)
            """,
                (memory_id, node_id, score),
            )

        populated_db.commit()

        # Query with aggregated activations
        cursor.execute(
            """
            SELECT m.*,
                   GROUP_CONCAT(n.name || ':' || ma.activation_score) as activations
            FROM memories m
            JOIN memory_activations ma ON m.memory_id = ma.memory_id
            JOIN nodes n ON ma.node_id = n.id
            WHERE m.memory_id = ?
            GROUP BY m.id
        """,
            (memory_id,),
        )

        result = cursor.fetchone()
        assert result is not None
        assert result["activations"] is not None
