# Hebbian Mind Enterprise - Test Suite

Comprehensive test suite for Hebbian Mind Enterprise Edition.

## Author

CIPS LLC

## Test Structure

```
tests/
├── __init__.py              # Package init
├── conftest.py              # Pytest fixtures and configuration
├── test_graph.py            # Node and edge operations
├── test_hebbian.py          # Hebbian learning (co-activation strengthening)
├── test_mcp_server.py       # MCP protocol tests
└── test_persistence.py      # Dual-write RAM+disk tests
```

## Running Tests

### Install Dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- pytest
- pytest-asyncio
- black
- ruff

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_graph.py
pytest tests/test_hebbian.py
pytest tests/test_mcp_server.py
pytest tests/test_persistence.py
```

### Run Specific Test Class or Function

```bash
pytest tests/test_graph.py::TestNodeOperations
pytest tests/test_hebbian.py::TestHebbianStrengthening::test_edge_strengthening_with_cap
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=hebbian_mind --cov-report=html
```

## Test Categories

### Markers

Tests are marked with the following categories:

- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.integration` - Integration tests requiring multiple components
- `@pytest.mark.requires_ram` - Tests requiring RAM disk access
- `@pytest.mark.requires_faiss` - Tests requiring FAISS tether
- `@pytest.mark.requires_precog` - Tests requiring PRECOG integration

### Skip Tests by Marker

```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m "integration"

# Skip tests requiring RAM disk
pytest -m "not requires_ram"
```

## Test Fixtures

### Core Fixtures (conftest.py)

- `temp_dir` - Temporary directory for test data
- `test_config` - Test configuration with temporary paths
- `mock_config` - Mocked Config class
- `sample_nodes` - Sample test nodes
- `nodes_file` - Sample nodes.json file
- `test_db` - Test database connection with schema
- `populated_db` - Database populated with test nodes
- `mock_faiss_tether` - Mocked FAISS tether
- `mock_precog` - Mocked PRECOG concept extractor

### Using Fixtures

```python
def test_example(populated_db, sample_nodes):
    cursor = populated_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM nodes")
    count = cursor.fetchone()[0]
    assert count == len(sample_nodes)
```

## Test Coverage

### test_graph.py

Tests for graph operations:
- Node insertion and retrieval
- Edge creation and manipulation
- Category-based edges
- Node-edge relationships
- Graph queries

### test_hebbian.py

Tests for Hebbian learning:
- Node activation and scoring
- Keyword and phrase matching
- Edge strengthening ("neurons that fire together, wire together")
- Co-activation tracking
- Memory-node associations

### test_mcp_server.py

Tests for MCP protocol:
- Tool schema validation
- save_to_mind tool
- query_mind tool
- analyze_content tool
- get_related_nodes tool
- status tool
- list_nodes tool
- Error handling
- Integration workflows

### test_persistence.py

Tests for persistence layer:
- Disk-only mode
- RAM disk detection
- Dual-write mode (RAM + Disk)
- Disk-to-RAM synchronization
- Write failure handling
- WAL mode
- Nodes file loading
- Data integrity

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run tests
        run: |
          pytest -v --cov=hebbian_mind
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Mocking Strategy

Tests use mocking to:
1. **Isolate filesystem operations** - All tests use temporary directories
2. **Mock external services** - FAISS tether and PRECOG are mocked
3. **Environment independence** - Tests run without requiring specific system configuration
4. **Fast execution** - No actual RAM disk or external dependencies needed

## Environment Variables

Tests reset these environment variables before each test:

- `HEBBIAN_MIND_BASE_DIR`
- `HEBBIAN_MIND_RAM_DISK`
- `HEBBIAN_MIND_RAM_DIR`
- `HEBBIAN_MIND_FAISS_ENABLED`
- `HEBBIAN_MIND_PRECOG_ENABLED`
- `HEBBIAN_MIND_THRESHOLD`
- `HEBBIAN_MIND_EDGE_FACTOR`
- `HEBBIAN_MIND_MAX_WEIGHT`

## Continuous Testing

### Watch Mode (requires pytest-watch)

```bash
pip install pytest-watch
ptw
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest -x
```

## Troubleshooting

### Import Errors

Ensure package is installed in development mode:
```bash
pip install -e .
```

### Async Test Failures

Ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```

### Temporary Directory Issues

Tests clean up after themselves, but you can manually clean:
```bash
pytest --basetemp=/tmp/pytest-custom
```

## Best Practices

1. **Isolation** - Each test is independent and doesn't rely on others
2. **Mocking** - External dependencies are mocked for reliability
3. **Cleanup** - Temporary files are automatically cleaned up
4. **Assertions** - Clear, specific assertions that explain failures
5. **Documentation** - Each test has a clear docstring

## Contributing

When adding new tests:

1. Add appropriate fixtures to `conftest.py` if needed
2. Mark tests with appropriate markers (`@pytest.mark.slow`, etc.)
3. Ensure tests are isolated and don't depend on execution order
4. Add docstrings explaining what is being tested
5. Use meaningful assertion messages

## License

Copyright (c) 2026 CIPS LLC. All rights reserved.
