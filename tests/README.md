# env-doctor Test Suite

This directory contains the comprehensive test suite for env-doctor, covering unit tests, integration tests, and performance tests.

## Test Structure

```
tests/
├── README.md                    # This file
├── test_cli.py                  # CLI command tests
├── test_compiler.py             # Database compiler tests
├── test_core.py                 # Core analysis and matching tests
├── test_database.py             # Database operations tests
├── test_integration.py          # Integration and workflow tests
├── test_recommendations.py      # Recommendation engine tests
├── test_reporting.py            # Reporting system tests
├── test_scanner.py              # Package scanner tests
├── test_utils.py                # Utility module tests
├── test_vram.py                 # VRAM estimation tests
└── verify_*.py                  # Verification scripts
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src/env_doctor --cov-report=term-missing --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/test_cli.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_cli.py::TestCheckCommand -v
```

### Run Specific Test
```bash
pytest tests/test_cli.py::TestCheckCommand::test_check_missing_file -v
```

### Run Tests Matching Pattern
```bash
pytest -k "test_version" -v
```

## Test Categories

### Unit Tests
Test individual functions and classes in isolation:
- `test_core.py` - Version matching, severity scoring, analysis
- `test_database.py` - Database models and operations
- `test_scanner.py` - PyPI client, dependency parser, wheel extractor
- `test_vram.py` - VRAM calculation components
- `test_utils.py` - Configuration and requirements parsing

### Integration Tests
Test multiple components working together:
- `test_integration.py` - End-to-end workflows
  - Database + Scanner integration
  - Recommendation workflows
  - VRAM estimation pipelines
  - Analysis report generation
  - Error handling across components

### CLI Tests
Test command-line interface:
- `test_cli.py` - All CLI commands
  - `check` - Dependency checking
  - `inspect` - Environment inspection
  - `patch` - Dependency patching
  - `recommend` - Stack recommendations
  - `report` - Error reporting
  - `update` - Database updates
  - `vram` - VRAM estimation

### Performance Tests
Basic performance benchmarks included in `test_integration.py`:
- Version matching with large datasets
- Database query performance
- Bulk operations

## Coverage Requirements

The project maintains >80% test coverage across all modules:

### Current Coverage Targets
- **Core modules**: >80% coverage
- **CLI modules**: >70% coverage
- **Database modules**: >85% coverage
- **Scanner modules**: >75% coverage
- **VRAM modules**: >80% coverage
- **Utils modules**: >85% coverage

### Viewing Coverage Reports

After running tests with coverage, open the HTML report:
```bash
# Windows
start htmlcov/index.html

# Linux/Mac
open htmlcov/index.html
```

## Writing Tests

### Test Naming Convention
- Test files: `test_<module>.py`
- Test classes: `Test<Component>`
- Test functions: `test_<what_it_tests>`

### Example Test Structure
```python
class TestMyComponent:
    """Test MyComponent class."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        component = MyComponent()
        result = component.do_something()
        assert result == expected_value
    
    def test_error_handling(self):
        """Test error handling."""
        component = MyComponent()
        with pytest.raises(ValueError):
            component.do_invalid_thing()
    
    def test_with_mock(self, mocker):
        """Test with mocked dependencies."""
        mock_dep = mocker.patch('module.dependency')
        mock_dep.return_value = "mocked"
        
        component = MyComponent()
        result = component.use_dependency()
        assert result == "mocked"
```

### Using Fixtures
```python
@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}

def test_with_fixture(sample_data):
    """Test using fixture."""
    assert sample_data["key"] == "value"
```

### Temporary Files
```python
def test_with_temp_file(tmp_path):
    """Test with temporary file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    assert test_file.read_text() == "content"
```

## Mocking Guidelines

### Mock External APIs
Always mock external API calls (PyPI, HuggingFace, etc.):
```python
@patch('env_doctor.scanner.pypi_client.httpx.get')
def test_api_call(mock_get):
    mock_get.return_value.json.return_value = {"info": {"version": "1.0.0"}}
    # Test code here
```

### Mock File System Operations
Mock file operations when testing error conditions:
```python
@patch('pathlib.Path.exists')
def test_missing_file(mock_exists):
    mock_exists.return_value = False
    # Test code here
```

### Mock Database Operations
Use temporary databases for integration tests:
```python
def test_database_operation(tmp_path):
    db_path = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_path))
    # Test code here
```

## Test Data

### Sample Requirements Files
Create temporary requirements files for testing:
```python
def test_parse_requirements(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("numpy>=1.20.0\npandas>=1.3.0\n")
    # Test parsing
```

### Sample Database Records
Use factories or builders for test data:
```python
def create_test_package(name="test", version="1.0.0"):
    return Package(
        uid=f"pkg_{name}",
        name=name,
        description=f"Test package {name}"
    )
```

## Continuous Integration

Tests run automatically on:
- Every push to main branch
- Every pull request
- Scheduled daily runs

### CI Configuration
See `.github/workflows/ci.yml` for CI setup.

### Required Checks
- All tests must pass
- Coverage must be >80%
- No linting errors
- Type checking passes

## Debugging Tests

### Run with Verbose Output
```bash
pytest -vv
```

### Show Print Statements
```bash
pytest -s
```

### Stop on First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Debug with PDB
```bash
pytest --pdb
```

## Common Issues

### Import Errors
Ensure env-doctor is installed in development mode:
```bash
pip install -e .
```

### Database Locked Errors
Use temporary databases in tests to avoid conflicts:
```python
def test_something(tmp_path):
    db_path = tmp_path / "test.db"
    # Use db_path for testing
```

### Slow Tests
Mark slow tests and skip them during development:
```python
@pytest.mark.slow
def test_slow_operation():
    # Slow test code
```

Run without slow tests:
```bash
pytest -m "not slow"
```

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure tests cover edge cases
3. Add integration tests for workflows
4. Update this README if adding new test categories
5. Maintain >80% coverage

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)

## Contact

For questions about testing, please open an issue on GitHub.