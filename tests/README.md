# KALAP V2 Test Suite - Quick Reference

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── unit/                # Individual module tests
│   ├── test_fuzzy_matcher.py
│   ├── test_context_tracker.py
│   ├── test_answer_validator.py
│   ├── test_question_router.py
│   └── test_phase_manager.py
└── integration/         # Multi-module orchestration tests
    └── test_response_generator.py
```

## Run Commands

### Run All Tests
```bash
pytest
```

### Run Specific Test Groups
```bash
pytest -m unit                    # Unit tests only
pytest -m integration             # Integration tests only
pytest -m fast                    # Fast tests (< 1s)
pytest -m fuzzy                   # Fuzzy matcher tests
pytest -m context                 # Context tracker tests
```

### Run Specific Test File
```bash
pytest tests/unit/test_fuzzy_matcher.py
pytest tests/integration/test_response_generator.py
```

### Run Specific Test Class or Function
```bash
pytest tests/unit/test_fuzzy_matcher.py::TestFuzzyMatcherIntents
pytest tests/unit/test_fuzzy_matcher.py::TestFuzzyMatcherIntents::test_exact_keyword_match
```

### Run with Coverage
```bash
pytest --cov=kalap_v2 --cov-report=html
```
Opens `htmlcov/index.html` for detailed coverage report.

### Run in Verbose Mode
```bash
pytest -v
```

### Run Failed Tests Only
```bash
pytest --lf
```

### Run Tests in Parallel (requires pytest-xdist)
```bash
pytest -n auto
```

## Test Organization

- **Unit Tests**: Test individual modules in isolation
  - Fast execution (< 1s per test)
  - No dependencies between tests
  - Focus on Single Responsibility Principle

- **Integration Tests**: Test module interactions
  - Test full conversation flows
  - Validate loose coupling between modules
  - May be slower (marked with `@pytest.mark.slow`)

## Test Markers

- `@pytest.mark.unit`: Unit test
- `@pytest.mark.integration`: Integration test
- `@pytest.mark.fast`: Fast-running test
- `@pytest.mark.slow`: Slow-running test
- `@pytest.mark.fuzzy`: Fuzzy matcher module
- `@pytest.mark.context`: Context tracker module
- `@pytest.mark.validator`: Answer validator module
- `@pytest.mark.router`: Question router module
- `@pytest.mark.phase`: Phase manager module
- `@pytest.mark.generator`: Response generator module

## Rationale for Structure

- **Modular Design**: Tests organized by module for easy navigation
- **High Cohesion**: Related tests grouped together
- **Loose Coupling**: Tests can run independently or in groups
- **Regression Testing**: Clear outcomes for CI/CD validation
- **Minimalism**: No unnecessary test complexity
