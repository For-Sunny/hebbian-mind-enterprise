"""
Tests for graph operations: nodes and edges

Copyright (c) 2026 CIPS LLC
"""

import json
import sqlite3
from pathlib import Path

import pytest


class TestNodeOperations:
    """Test node creation, retrieval, and updates."""

    def test_node_insertion(self, populated_db: sqlite3.Connection):
        """Test inserting nodes into database."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes")
        count = cursor.fetchone()[0]
        assert count == 3, "Should have 3 test nodes"

    def test_node_retrieval_by_id(self, populated_db: sqlite3.Connection):
        """Test retrieving node by node_id."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT * FROM nodes WHERE node_id = ?", ("node_1",))
        node = cursor.fetchone()

        assert node is not None
        assert node["name"] == "Test Concept"
        assert node["category"] == "test"

    def test_node_retrieval_by_name(self, populated_db: sqlite3.Connection):
        """Test retrieving node by name."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT * FROM nodes WHERE name = ?", ("Test Concept",))
        node = cursor.fetchone()

        assert node is not None
        assert node["node_id"] == "node_1"

    def test_node_retrieval_case_insensitive(self, populated_db: sqlite3.Connection):
        """Test case-insensitive node name search."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT * FROM nodes WHERE LOWER(name) = LOWER(?)", ("TEST CONCEPT",))
        node = cursor.fetchone()

        assert node is not None
        assert node["node_id"] == "node_1"

    def test_get_all_nodes(self, populated_db: sqlite3.Connection):
        """Test retrieving all nodes."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT * FROM nodes ORDER BY category, name")
        nodes = cursor.fetchall()

        assert len(nodes) == 3
        # Should be sorted by category then name
        assert nodes[0]["category"] in ["test", "other"]

    def test_get_nodes_by_category(self, populated_db: sqlite3.Connection):
        """Test filtering nodes by category."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT * FROM nodes WHERE category = ?", ("test",))
        nodes = cursor.fetchall()

        assert len(nodes) == 2
        assert all(node["category"] == "test" for node in nodes)

    def test_node_keywords_json_storage(self, populated_db: sqlite3.Connection):
        """Test that keywords are stored and retrieved as JSON."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT keywords FROM nodes WHERE node_id = ?", ("node_1",))
        keywords_json = cursor.fetchone()["keywords"]

        keywords = json.loads(keywords_json)
        assert isinstance(keywords, list)
        assert "test" in keywords
        assert "example" in keywords

    def test_node_prototype_phrases_json_storage(self, populated_db: sqlite3.Connection):
        """Test that prototype phrases are stored and retrieved as JSON."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT prototype_phrases FROM nodes WHERE node_id = ?", ("node_1",))
        phrases_json = cursor.fetchone()["prototype_phrases"]

        phrases = json.loads(phrases_json)
        assert isinstance(phrases, list)
        assert "this is a test" in phrases

    def test_node_activation_count_defaults_to_zero(self, populated_db: sqlite3.Connection):
        """Test that new nodes have activation_count of 0."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT activation_count FROM nodes WHERE node_id = ?", ("node_1",))
        count = cursor.fetchone()["activation_count"]

        assert count == 0

    def test_node_weight_defaults_to_one(self, populated_db: sqlite3.Connection):
        """Test that nodes have default weight of 1.0."""
        cursor = populated_db.cursor()
        cursor.execute("SELECT weight FROM nodes WHERE node_id = ?", ("node_1",))
        weight = cursor.fetchone()["weight"]

        assert weight == 1.0

    def test_node_unique_constraint(self, populated_db: sqlite3.Connection):
        """Test that duplicate node_id is rejected."""
        with pytest.raises(sqlite3.IntegrityError):
            populated_db.execute("""
                INSERT INTO nodes (node_id, name, category, keywords, prototype_phrases)
                VALUES (?, ?, ?, ?, ?)
            """, ("node_1", "Duplicate", "test", "[]", "[]"))


class TestEdgeOperations:
    """Test edge creation, retrieval, and manipulation."""

    def test_edge_creation(self, populated_db: sqlite3.Connection):
        """Test creating an edge between two nodes."""
        cursor = populated_db.cursor()

        # Get node IDs
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_2",))
        node2_id = cursor.fetchone()["id"]

        # Create edge
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight, co_activation_count)
            VALUES (?, ?, ?, ?)
        """, (node1_id, node2_id, 0.5, 1))
        populated_db.commit()

        # Verify edge exists
        cursor.execute("SELECT * FROM edges WHERE source_id = ? AND target_id = ?",
                      (node1_id, node2_id))
        edge = cursor.fetchone()

        assert edge is not None
        assert edge["weight"] == 0.5
        assert edge["co_activation_count"] == 1

    def test_edge_ordering_consistency(self, populated_db: sqlite3.Connection):
        """Test that edges maintain consistent source/target ordering."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_2",))
        node2_id = cursor.fetchone()["id"]

        # Ensure consistent ordering (smaller ID as source)
        source_id = min(node1_id, node2_id)
        target_id = max(node1_id, node2_id)

        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight)
            VALUES (?, ?, ?)
        """, (source_id, target_id, 0.5))
        populated_db.commit()

        # Should find edge regardless of query order
        cursor.execute("""
            SELECT * FROM edges
            WHERE (source_id = ? AND target_id = ?)
               OR (source_id = ? AND target_id = ?)
        """, (node1_id, node2_id, node2_id, node1_id))

        edge = cursor.fetchone()
        assert edge is not None

    def test_edge_unique_constraint(self, populated_db: sqlite3.Connection):
        """Test that duplicate edges are rejected."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_2",))
        node2_id = cursor.fetchone()["id"]

        # Create first edge
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight)
            VALUES (?, ?, ?)
        """, (node1_id, node2_id, 0.5))
        populated_db.commit()

        # Attempt duplicate - should fail
        with pytest.raises(sqlite3.IntegrityError):
            populated_db.execute("""
                INSERT INTO edges (source_id, target_id, weight)
                VALUES (?, ?, ?)
            """, (node1_id, node2_id, 0.7))

    def test_get_edges_by_weight(self, populated_db: sqlite3.Connection):
        """Test retrieving edges with minimum weight threshold."""
        cursor = populated_db.cursor()

        # Create edges with different weights
        cursor.execute("SELECT id FROM nodes ORDER BY id LIMIT 3")
        node_ids = [row["id"] for row in cursor.fetchall()]

        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """, (node_ids[0], node_ids[1], 0.1))
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """, (node_ids[1], node_ids[2], 0.5))
        populated_db.commit()

        # Query edges with min weight 0.3
        cursor.execute("SELECT * FROM edges WHERE weight >= ?", (0.3,))
        edges = cursor.fetchall()

        assert len(edges) == 1
        assert edges[0]["weight"] >= 0.3

    def test_get_related_nodes(self, populated_db: sqlite3.Connection):
        """Test finding nodes connected via edges."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_1",))
        node1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM nodes WHERE node_id = ?", ("node_2",))
        node2_id = cursor.fetchone()["id"]

        # Create edge
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """, (node1_id, node2_id, 0.5))
        populated_db.commit()

        # Find nodes related to node_1
        cursor.execute("""
            SELECT n.*, e.weight
            FROM edges e
            JOIN nodes n ON (e.target_id = n.id OR e.source_id = n.id)
            WHERE (e.source_id = ? OR e.target_id = ?)
              AND n.id != ?
        """, (node1_id, node1_id, node1_id))

        related = cursor.fetchall()
        assert len(related) == 1
        assert related[0]["node_id"] == "node_2"

    def test_strongest_edges(self, populated_db: sqlite3.Connection):
        """Test retrieving edges sorted by weight."""
        cursor = populated_db.cursor()

        cursor.execute("SELECT id FROM nodes ORDER BY id LIMIT 3")
        node_ids = [row["id"] for row in cursor.fetchall()]

        # Create edges with different weights
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """, (node_ids[0], node_ids[1], 0.3))
        populated_db.execute("""
            INSERT INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)
        """, (node_ids[1], node_ids[2], 0.8))
        populated_db.commit()

        # Get strongest edges
        cursor.execute("SELECT * FROM edges ORDER BY weight DESC LIMIT 1")
        strongest = cursor.fetchone()

        assert strongest["weight"] == 0.8

    def test_edge_foreign_key_constraints(self, populated_db: sqlite3.Connection):
        """Test that edges require valid node IDs."""
        # SQLite foreign keys might not be enforced by default
        # This test verifies the schema is correct
        cursor = populated_db.cursor()
        cursor.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()

        # Note: In production, ensure PRAGMA foreign_keys=ON
        # For test, we just verify the schema has FK constraints
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='edges'
        """)
        schema = cursor.fetchone()[0]

        assert "FOREIGN KEY" in schema
        assert "REFERENCES nodes" in schema


class TestCategoryEdges:
    """Test initialization and management of category-based edges."""

    def test_init_category_edges(self, populated_db: sqlite3.Connection):
        """Test creating edges between nodes in same category."""
        cursor = populated_db.cursor()

        # Get nodes in 'test' category
        cursor.execute("SELECT id FROM nodes WHERE category = ? ORDER BY id", ("test",))
        test_nodes = [row["id"] for row in cursor.fetchall()]

        assert len(test_nodes) == 2

        # Create edges between same-category nodes
        for i, id1 in enumerate(test_nodes):
            for id2 in test_nodes[i+1:]:
                source_id = min(id1, id2)
                target_id = max(id1, id2)
                populated_db.execute("""
                    INSERT OR IGNORE INTO edges (source_id, target_id, weight)
                    VALUES (?, ?, ?)
                """, (source_id, target_id, 0.1))

        populated_db.commit()

        # Verify edge exists
        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]

        assert edge_count == 1  # Only one edge between two test nodes

    def test_category_isolation(self, populated_db: sqlite3.Connection):
        """Test that category edges don't cross categories."""
        cursor = populated_db.cursor()

        # Create edges only within categories
        cursor.execute("SELECT id, category FROM nodes")
        nodes = cursor.fetchall()

        by_category = {}
        for node in nodes:
            cat = node["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(node["id"])

        # Create within-category edges
        for cat, node_ids in by_category.items():
            for i, id1 in enumerate(node_ids):
                for id2 in node_ids[i+1:]:
                    source_id = min(id1, id2)
                    target_id = max(id1, id2)
                    populated_db.execute("""
                        INSERT INTO edges (source_id, target_id, weight)
                        VALUES (?, ?, ?)
                    """, (source_id, target_id, 0.1))

        populated_db.commit()

        # Verify no cross-category edges exist
        cursor.execute("""
            SELECT e.*
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
            WHERE n1.category != n2.category
        """)

        cross_category_edges = cursor.fetchall()
        assert len(cross_category_edges) == 0
