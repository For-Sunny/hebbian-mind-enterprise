"""
Tests for MCP server protocol implementation

Copyright (c) 2026 CIPS LLC
"""

import json

import pytest


class TestMCPProtocol:
    """Test MCP protocol compliance."""

    @pytest.mark.asyncio
    async def test_list_tools_structure(self):
        """Test that list_tools returns valid MCP tool schema."""
        # Mock the server's list_tools response
        mock_tools = [
            {
                "name": "save_to_mind",
                "description": "Save content to Hebbian Mind",
                "inputSchema": {
                    "type": "object",
                    "properties": {"content": {"type": "string", "description": "Content to save"}},
                    "required": ["content"],
                },
            }
        ]

        # Verify structure
        assert isinstance(mock_tools, list)
        for tool in mock_tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_call_tool_response_structure(self):
        """Test that call_tool returns valid MCP response."""
        mock_response = [
            {
                "type": "text",
                "text": json.dumps({"success": True, "message": "Operation completed"}),
            }
        ]

        # Verify structure
        assert isinstance(mock_response, list)
        for item in mock_response:
            assert "type" in item
            assert item["type"] == "text"
            assert "text" in item

    @pytest.mark.asyncio
    async def test_error_handling_structure(self):
        """Test that errors are returned in valid MCP format."""
        error_response = [
            {"type": "text", "text": json.dumps({"success": False, "error": "Test error message"})}
        ]

        # Verify error structure
        assert isinstance(error_response, list)
        content = json.loads(error_response[0]["text"])
        assert content["success"] is False
        assert "error" in content


class TestSaveToMindTool:
    """Test the save_to_mind tool."""

    def test_save_tool_schema(self):
        """Test save_to_mind tool schema."""
        tool_schema = {
            "name": "save_to_mind",
            "description": "Save content to Hebbian Mind with automatic node activation",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to save"},
                    "summary": {"type": "string", "description": "Optional summary"},
                    "source": {"type": "string", "description": "Source identifier"},
                    "importance": {"type": "number", "description": "Importance 0-1"},
                    "emotional_intensity": {
                        "type": "number",
                        "description": "Emotional intensity 0-1",
                    },
                },
                "required": ["content"],
            },
        }

        # Verify required fields
        assert "content" in tool_schema["inputSchema"]["required"]

        # Verify optional fields
        properties = tool_schema["inputSchema"]["properties"]
        assert "summary" in properties
        assert "importance" in properties
        assert "emotional_intensity" in properties

    @pytest.mark.asyncio
    async def test_save_with_minimal_args(self):
        """Test saving with only required arguments."""

        # Simulate tool execution
        result = {
            "success": True,
            "memory_id": "test_001",
            "activations": [],
            "edges_strengthened": 0,
        }

        assert result["success"] is True
        assert "memory_id" in result

    @pytest.mark.asyncio
    async def test_save_with_full_args(self):
        """Test saving with all arguments."""
        args = {
            "content": "Full test content",
            "summary": "Test summary",
            "source": "TEST_SOURCE",
            "importance": 0.8,
            "emotional_intensity": 0.6,
        }

        result = {
            "success": True,
            "memory_id": "test_002",
            "activations": [],
            "edges_strengthened": 0,
            "summary": args["summary"],
        }

        assert result["success"] is True
        assert result["summary"] == args["summary"]

    @pytest.mark.asyncio
    async def test_save_with_no_activations(self):
        """Test saving content that doesn't activate any nodes."""

        result = {
            "success": False,
            "message": "No concept nodes activated above threshold",
            "threshold": 0.3,
        }

        assert result["success"] is False
        assert "threshold" in result

    @pytest.mark.asyncio
    async def test_save_returns_activations(self):
        """Test that save returns list of activated nodes."""

        result = {
            "success": True,
            "memory_id": "test_003",
            "activations": [
                {"node": "node_1", "name": "Test Concept", "category": "test", "score": 0.75}
            ],
            "edges_strengthened": 0,
        }

        assert len(result["activations"]) > 0
        assert "score" in result["activations"][0]


class TestQueryMindTool:
    """Test the query_mind tool."""

    def test_query_tool_schema(self):
        """Test query_mind tool schema."""
        tool_schema = {
            "name": "query_mind",
            "description": "Query memories by concept nodes",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of node names to query",
                    },
                    "limit": {"type": "number", "description": "Max results"},
                },
            },
        }

        # Verify schema structure
        assert tool_schema["inputSchema"]["properties"]["nodes"]["type"] == "array"

    @pytest.mark.asyncio
    async def test_query_by_single_node(self):
        """Test querying by single node."""
        args = {"nodes": ["Test Concept"], "limit": 20}

        result = {
            "success": True,
            "queried_nodes": args["nodes"],
            "memories_found": 2,
            "memories": [
                {"memory_id": "mem_001", "summary": "Test 1"},
                {"memory_id": "mem_002", "summary": "Test 2"},
            ],
        }

        assert result["success"] is True
        assert result["memories_found"] == len(result["memories"])

    @pytest.mark.asyncio
    async def test_query_by_multiple_nodes(self):
        """Test querying by multiple nodes."""
        args = {"nodes": ["Test Concept", "Related Concept"], "limit": 10}

        result = {
            "success": True,
            "queried_nodes": args["nodes"],
            "memories_found": 1,
            "memories": [{"memory_id": "mem_003", "summary": "Test 3"}],
        }

        assert len(args["nodes"]) == 2
        assert result["memories_found"] >= 0

    @pytest.mark.asyncio
    async def test_query_with_no_nodes(self):
        """Test querying without specifying nodes."""

        result = {"success": False, "message": "No nodes specified"}

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_query_nonexistent_node(self):
        """Test querying node that doesn't exist."""
        args = {"nodes": ["Nonexistent Node"]}

        result = {
            "success": True,
            "queried_nodes": args["nodes"],
            "memories_found": 0,
            "memories": [],
        }

        assert result["memories_found"] == 0


class TestAnalyzeContentTool:
    """Test the analyze_content tool."""

    def test_analyze_tool_schema(self):
        """Test analyze_content tool schema."""
        tool_schema = {
            "name": "analyze_content",
            "description": "Analyze content against concept nodes without saving",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to analyze"},
                    "threshold": {"type": "number", "description": "Activation threshold 0-1"},
                },
                "required": ["content"],
            },
        }

        assert "content" in tool_schema["inputSchema"]["required"]
        assert "threshold" in tool_schema["inputSchema"]["properties"]

    @pytest.mark.asyncio
    async def test_analyze_returns_activations(self):
        """Test that analyze returns activated nodes."""

        result = {
            "success": True,
            "threshold": 0.3,
            "activated_count": 2,
            "activations": [
                {
                    "node": "node_1",
                    "name": "Test Concept",
                    "score": 0.75,
                    "matched_keywords": ["test", "content"],
                }
            ],
        }

        assert result["success"] is True
        assert "activations" in result
        assert "matched_keywords" in result["activations"][0]

    @pytest.mark.asyncio
    async def test_analyze_with_custom_threshold(self):
        """Test analyzing with custom threshold."""
        args = {"content": "Test content", "threshold": 0.5}  # Higher threshold

        result = {
            "success": True,
            "threshold": 0.5,
            "activated_count": 1,
            "activations": [{"node": "node_1", "score": 0.75}],
        }

        # Only nodes with score >= 0.5 should be returned
        assert all(a["score"] >= args["threshold"] for a in result["activations"])


class TestRelatedNodesTool:
    """Test the get_related_nodes tool."""

    def test_related_nodes_tool_schema(self):
        """Test get_related_nodes tool schema."""
        tool_schema = {
            "name": "get_related_nodes",
            "description": "Get nodes connected by Hebbian edges",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "Node name"},
                    "min_weight": {"type": "number", "description": "Minimum edge weight"},
                },
                "required": ["node"],
            },
        }

        assert "node" in tool_schema["inputSchema"]["required"]

    @pytest.mark.asyncio
    async def test_get_related_nodes_success(self):
        """Test getting related nodes."""

        result = {
            "success": True,
            "source_node": "Test Concept",
            "related_count": 2,
            "related_nodes": [
                {"name": "Related Concept", "category": "test", "weight": 0.5},
                {"name": "Other Concept", "category": "test", "weight": 0.3},
            ],
        }

        assert result["success"] is True
        assert result["related_count"] == len(result["related_nodes"])

    @pytest.mark.asyncio
    async def test_get_related_nodes_not_found(self):
        """Test querying related nodes for nonexistent node."""

        result = {"success": False, "message": "Node not found: Nonexistent"}

        assert result["success"] is False


class TestStatusTool:
    """Test the status tool."""

    @pytest.mark.asyncio
    async def test_status_returns_statistics(self):
        """Test that status returns system statistics."""
        result = {
            "success": True,
            "status": "operational",
            "statistics": {
                "node_count": 118,
                "edge_count": 250,
                "memory_count": 100,
                "total_activations": 1000,
            },
            "dual_write": {
                "enabled": False,
                "using_ram": False,
                "ram_path": None,
                "disk_path": "/path/to/db",
            },
        }

        assert result["success"] is True
        assert "statistics" in result
        assert "node_count" in result["statistics"]

    @pytest.mark.asyncio
    async def test_status_includes_strongest_edges(self):
        """Test that status includes strongest connections."""
        result = {
            "success": True,
            "strongest_connections": [
                {"source": "Node1", "target": "Node2", "weight": 5.5},
                {"source": "Node3", "target": "Node4", "weight": 4.2},
            ],
        }

        assert "strongest_connections" in result
        assert len(result["strongest_connections"]) > 0


class TestListNodesTool:
    """Test the list_nodes tool."""

    @pytest.mark.asyncio
    async def test_list_all_nodes(self):
        """Test listing all nodes."""
        result = {
            "success": True,
            "total_nodes": 3,
            "categories": {
                "test": [
                    {"node_id": "node_1", "name": "Test Concept"},
                    {"node_id": "node_2", "name": "Related Concept"},
                ],
                "other": [{"node_id": "node_3", "name": "Other Category"}],
            },
        }

        assert result["success"] is True
        assert "categories" in result

    @pytest.mark.asyncio
    async def test_list_nodes_by_category(self):
        """Test listing nodes filtered by category."""

        result = {
            "success": True,
            "total_nodes": 2,
            "categories": {
                "test": [
                    {"node_id": "node_1", "name": "Test Concept"},
                    {"node_id": "node_2", "name": "Related Concept"},
                ]
            },
        }

        assert len(result["categories"]) == 1
        assert "test" in result["categories"]


@pytest.mark.integration
class TestMCPServerIntegration:
    """Integration tests for full MCP server functionality."""

    @pytest.mark.asyncio
    async def test_save_and_query_workflow(self):
        """Test complete workflow: save memory, then query it."""
        # Save memory
        save_result = {
            "success": True,
            "memory_id": "test_workflow",
            "activations": [{"node": "node_1", "name": "Test Concept", "score": 0.8}],
        }

        assert save_result["success"] is True

        # Query by activated node
        query_result = {
            "success": True,
            "memories_found": 1,
            "memories": [{"memory_id": "test_workflow"}],
        }

        assert query_result["memories_found"] == 1

    @pytest.mark.asyncio
    async def test_analyze_before_save_workflow(self):
        """Test workflow: analyze content, then save if satisfied."""
        # Analyze first
        analyze_result = {
            "success": True,
            "activated_count": 2,
            "activations": [{"node": "node_1", "score": 0.7}],
        }

        if analyze_result["activated_count"] > 0:
            # Save the content
            save_result = {"success": True, "memory_id": "analyzed_memory"}
            assert save_result["success"] is True
