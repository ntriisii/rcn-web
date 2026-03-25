# Test Suite for Events & Target Loading

## TL;DR
> **Quick Summary**: Create comprehensive pytest test suite for all event handlers and target loading functionality in rcn-web, following rcn-core patterns.
>
> **Deliverables**:
> - pytest infrastructure (pytest.ini, conftest.py, dependencies)
> - Tests for 11 `@rcn_event` handlers across 6 files
> - Tests for scope.py pure functions
> - Tests for utils.py functions used by events
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Infrastructure → Scope tests → Event tests → Final verification

---

## Context

### Original Request
Build tests for events and target loading in rcn-web, checking rcn-core tests to avoid duplication.

### Interview Summary
**Key Discussions**:
- Scope: ALL event handlers (core + scanning) - 11 handlers across 6 files
- Infrastructure: Create pytest setup from scratch (no existing pytest config)
- Priority: Event handlers first, then pure utility functions
- Pattern: Follow rcn-core's pytest-asyncio approach

**Research Findings**:
- rcn-core already tests: `@rcn_event` decorator, `TimeEvent`, `TargetStorage` basics, `get_unprocessed_entries`, cursor persistence
- rcn-web has 8 ad-hoc test scripts, no pytest configuration
- Event handlers are async, use `get_unprocessed_entries` with `web_match_storage`
- Scope.py has pure functions that can be tested without mocks

### Metis Review
**Identified Gaps** (addressed):
- Test isolation strategy: Use in-memory SQLite like rcn-core
- External dependencies: Mock subprocess, HTTP, WebSocket, file I/O
- AI handlers: Mock AI calls entirely
- Headless browser: Mock entirely, don't require in CI
- Coverage: Each handler needs happy path + empty input + error path

---

## Work Objectives

### Core Objective
Create a comprehensive pytest test suite for all event handlers and target loading utilities, ensuring tests run without external services.

### Concrete Deliverables
- `pytest.ini` with asyncio configuration
- `tests/conftest.py` with reusable fixtures
- Updated `pyproject.toml` with test dependencies
- Test files mirroring package structure:
  - `tests/core/test_events.py`
  - `tests/core/test_scope.py`
  - `tests/scanning/test_mcp_scanners.py`
  - `tests/scanning/test_client_side.py`
  - `tests/scanning/test_scanning_utils.py`
  - `tests/scanning/test_app_scans.py`
  - `tests/scanning/test_js_analysis.py`

### Definition of Done
- [x] All tests pass: `pytest tests/ -v`
- [x] Each handler has: happy path, empty input, error path tests
- [x] No external services required (all mocked)
- [x] Coverage report generated: `pytest --cov=rcn_web`

### Must Have
- pytest infrastructure with pytest-asyncio
- Tests for all 11 `@rcn_event` handlers
- Tests for `check_domain_in_scope` pure function
- Mocking for all external dependencies

### Must NOT Have (Guardrails)
- DO NOT test `@rcn_event` decorator (rcn-core responsibility)
- DO NOT test `TargetStorage` internals (rcn-core responsibility)
- DO NOT test `get_unprocessed_entries` context manager (rcn-core responsibility)
- DO NOT add tests for FastAPI routes (out of scope)
- DO NOT add tests for storage handlers (out of scope)
- DO NOT require external services to run tests

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (creating from scratch)
- **Automated tests**: YES (TDD approach)
- **Framework**: pytest with pytest-asyncio
- **Pattern**: Mock external deps, use fixtures for storage

### QA Policy
Every task includes agent-executed QA scenarios:
- **Unit tests**: pytest with mocked dependencies
- **Async tests**: pytest-asyncio with `asyncio_mode = auto`
- **Coverage**: pytest-cov for coverage reporting

---

## Execution Strategy

### Parallel Execution Waves
```
Wave 1 (Infrastructure - foundation):
├── Task 1: pytest.ini configuration [quick]
├── Task 2: pyproject.toml test dependencies [quick]
└── Task 3: tests/conftest.py with fixtures [quick]

Wave 2 (Pure functions - quick wins):
├── Task 4: tests/core/test_scope.py [quick]
└── Task 5: tests/core/__init__.py [quick]

Wave 3 (Core event handlers):
├── Task 6: tests/core/test_events.py - handle_init_target [unspecified-high]
└── Task 7: tests/scanning/__init__.py [quick]

Wave 4 (Scanning event handlers - MAX PARALLEL):
├── Task 8: tests/scanning/test_mcp_scanners.py (4 handlers) [unspecified-high]
├── Task 9: tests/scanning/test_client_side.py (1 handler) [unspecified-high]
├── Task 10: tests/scanning/test_scanning_utils.py (3 handlers) [unspecified-high]
├── Task 11: tests/scanning/test_app_scans.py (1 handler) [unspecified-high]
└── Task 12: tests/scanning/test_js_analysis.py (1 handler) [unspecified-high]

Wave FINAL (Verification):
├── Task F1: Full test suite run [quick]
├── Task F2: Coverage report generation [quick]
├── Task F3: Lint/type check [quick]
└── Task F4: Final verification [quick]
```

### Dependency Matrix
- **1-3**: — — 4-7, 1
- **4**: 3 — 5, 1
- **6**: 3 — 7-12, 1
- **7**: 3 — 8-12, 1
- **8-12**: 3, 6, 7 — F1, 1
- **F1-F4**: 8-12 — —

### Agent Dispatch Summary
- **Wave 1**: 3 tasks → `quick`
- **Wave 2**: 2 tasks → `quick`
- **Wave 3**: 2 tasks → 1 `unspecified-high`, 1 `quick`
- **Wave 4**: 5 tasks → `unspecified-high`
- **FINAL**: 4 tasks → `quick`

---

## TODOs

- [x] 1. Create pytest.ini configuration
- [x] 2. Add test dependencies to pyproject.toml
- [x] 3. Create tests/conftest.py with fixtures

 **What to do**:
 - Create `tests/` directory
 - Create `tests/conftest.py` with reusable fixtures:
   - `mock_target_storage` - Mock TargetStorage with common methods
   - `mock_event` - Minimal event dict for @rcn_event handlers
   - `mock_scheduled_md` - Scheduled metadata dict
   - `mock_web_match_storage` - Patched web_match_storage function
 - Add `tests/__init__.py`

 **Must NOT do**:
 - DO NOT import fixtures from rcn-core (maintain independence)
 - DO NOT create fixtures for @rcn_event decorator (rcn-core tests that)
 - DO NOT over-engineer fixtures - keep them minimal

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - Reason: Standard pytest fixture setup, well-defined scope
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: YES
 - **Parallel Group**: Wave 1 (with Tasks 1, 2)
 - **Blocks**: All test files (need fixtures)
 - **Blocked By**: None

 **References**:
 - `/home/ahmed/programming-projects/python/rcn-core/tests/conftest.py` - Reference fixture patterns
 - `/home/ahmed/programming-projects/python/rcn-web/rcn_web/core/events.py` - See what fixtures are needed

  **Acceptance Criteria**:
  - [x] `tests/conftest.py` exists with fixtures
  - [x] `tests/__init__.py` exists
  - [x] Fixtures are importable by test files
  - [x] Sample test using fixture runs successfully

 **QA Scenarios**:
 ```
 Scenario: Fixtures are available to test files
 Tool: Bash
 Preconditions: tests/conftest.py created with fixtures
 Steps:
   1. Create temporary test file using mock_target_storage
   2. Run `pytest tests/ -k "temp" --collect-only`
   3. Verify fixture is discovered
 Expected Result: Test collects successfully, fixture resolved
 Failure Indicators: "fixture not found", collection errors
 Evidence: .sisyphus/evidence/task-3-fixtures.txt
 ```

 **Commit**: YES (groups with Task 1, 2)
 - Message: `test: add pytest infrastructure`

---

- [x] 4. Create tests/core/test_scope.py for pure functions

 **What to do**:
 - Create `tests/core/` directory and `tests/core/__init__.py`
 - Test `check_domain_in_scope(domain, scope)` with:
   - Domain matches URL exactly
   - Domain matches wildcard pattern
   - Domain doesn't match
   - Empty domain (returns False)
   - Empty scope (returns False)
   - Complex wildcard patterns (*.example.com, *.example.*)

 **Must NOT do**:
 - DO NOT test `get_target_scope()` (reads globals, needs mocking)
 - DO NOT test `flow_in_scope()` (impure, needs mocking)
 - DO NOT import rcn_core.globals in tests

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - Reason: Pure function tests, no mocking needed
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: NO (needs conftest.py)
 - **Parallel Group**: Wave 2 (after Task 3)
 - **Blocks**: None (independent module)
 - **Blocked By**: Task 3 (conftest.py)

 **References**:
 - `/home/ahmed/programming-projects/python/rcn-web/rcn_web/core/scope.py:check_domain_in_scope` - Function under test

  **Acceptance Criteria**:
  - [x] `tests/core/test_scope.py` exists
  - [x] All test cases pass: `pytest tests/core/test_scope.py -v`
  - [x] Coverage shows `check_domain_in_scope` covered

 **QA Scenarios**:
 ```
 Scenario: Pure function tests pass without mocks
 Tool: Bash
 Preconditions: tests/core/test_scope.py created
 Steps:
   1. Run `pytest tests/core/test_scope.py -v`
   2. Verify all test cases pass
 Expected Result: X passed, 0 failed, no errors
 Failure Indicators: FAILED, ERROR in output
 Evidence: .sisyphus/evidence/task-4-scope-tests.txt
 ```

 **Commit**: YES
 - Message: `test: add scope.py pure function tests`

---

- [x] 5. Create tests/core/__init__.py

 **What to do**:
 - Create `tests/core/__init__.py` (empty or minimal)
 - Ensures tests/core is a valid Python package

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: YES
 - **Parallel Group**: Wave 2 (with Task 4)
 - **Blocked By**: Task 3 (conftest.py)

 **Commit**: YES (groups with Task 4)

---

- [x] 6. Create tests/core/test_events.py for handle_init_target

 **What to do**:
 - Test `handle_init_target(event, scheduled_md)` with:
   - **Happy path**: Mock get_unprocessed_entries returns valid entries, verify:
     - Domains written to file
     - Storage updated with domains
     - Metadata flags set correctly
   - **Empty entries**: Mock returns empty, handler returns early
   - **Error path**: Flow execution raises exception, verify:
     - init-recon-running flag reset
     - Exception re-raised
 - Mock: RCN_FLOWS, get_unprocessed_entries, file I/O, storage methods

 **Must NOT do**:
 - DO NOT call real flows or access real storage
 - DO NOT create integration tests that need real targets
 - DO NOT test RCN_FLOWS internals

 **Recommended Agent Profile**:
 - **Category**: `unspecified-high`
 - Reason: Complex async handler with multiple mocks, requires careful setup
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: NO (needs conftest.py)
 - **Parallel Group**: Wave 3
 - **Blocks**: None (independent)
 - **Blocked By**: Task 3

 **References**:
 - `/home/ahmed/programming-projects/python/rcn-web/rcn_web/core/events.py:handle_init_target` - Handler under test
 - `/home/ahmed/programming-projects/python/rcn-core/tests/test_events_complex.py` - Reference async event testing

  **Acceptance Criteria**:
  - [x] `tests/core/test_events.py` exists
  - [x] Happy path test passes
  - [x] Empty entries test passes
  - [x] Error path test passes
  - [x] `pytest tests/core/test_events.py -v` passes all

 **QA Scenarios**:
 ```
 Scenario: Event handler test with mocked dependencies
 Tool: Bash
 Preconditions: tests/core/test_events.py created
 Steps:
   1. Run `pytest tests/core/test_events.py -v`
   2. Verify 3+ tests pass (happy, empty, error)
 Expected Result: All tests pass, no external calls made
 Failure Indicators: "connection refused", "file not found", FAILED
 Evidence: .sisyphus/evidence/task-6-events-tests.txt
 ```

 **Commit**: YES
 - Message: `test: add events.py handler tests`

---

- [x] 7. Create tests/scanning/__init__.py

 **What to do**:
 - Create `tests/scanning/__init__.py`
 - Ensures tests/scanning is a valid Python package

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: YES
 - **Parallel Group**: Wave 3 (with Task 6)
 - **Blocked By**: Task 3

 **Commit**: YES (groups with scanning tests)

---

- [x] 8. Create tests/scanning/test_mcp_scanners.py (4 handlers)
- [x] 9. Create tests/scanning/test_client_side.py (1 handler)
- [x] 10. Create tests/scanning/test_scanning_utils.py (3 handlers)
- [x] 11. Create tests/scanning/test_app_scans.py (1 handler)
- [x] 12. Create tests/scanning/test_js_analysis.py (1 handler)

 **What to do**:
 - Test `js_intelligence_monitor` in `js_analysis.py`:
   - Mock RemoteFlowsAdapter (HTTP)
   - Mock storage operations
   - Happy path: JS files collected and stored
   - Empty entries: early return
   - Error path: HTTP failure

 **Must NOT do**:
 - DO NOT make real HTTP requests
 - DO NOT test RemoteFlowsAdapter class itself

 **Recommended Agent Profile**:
 - **Category**: `unspecified-high`
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: YES
 - **Parallel Group**: Wave 4 (with Tasks 8-11)
 - **Blocked By**: Task 3, Task 7

 **References**:
 - `/home/ahmed/programming-projects/python/rcn-web/rcn_web/scanning/js_analysis.py:js_intelligence_monitor`

  **Acceptance Criteria**:
  - [x] Handler has happy + empty + error tests
  - [x] `pytest tests/scanning/test_js_analysis.py -v` passes

 **Commit**: YES (groups with Task 8-11)

---

## Final Verification Wave

- [x] F1. **Full Test Suite Run** — Run `pytest tests/ -v` and verify all tests pass
- [x] F2. **Coverage Report** — Run `pytest --cov=rcn_web --cov-report=term-missing` and review coverage
- [x] F3. **Lint/Type Check** — Run `ruff check tests/` and `mypy tests/` (if configured)
- [x] F4. **Final Verification** — Review all test files for completeness, verify no external services required

---

## Commit Strategy

- **1**: `test: add pytest infrastructure` — pytest.ini, tests/conftest.py, pyproject.toml
- **2**: `test: add scope.py pure function tests` — tests/core/test_scope.py
- **3**: `test: add events.py handler tests` — tests/core/test_events.py
- **4**: `test: add scanning handler tests` — tests/scanning/*.py

---

## Success Criteria

### Verification Commands
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=rcn_web --cov-report=html

# Verify no external services
pytest tests/ -v --tb=short
```

  ### Final Checklist
  - [x] All 11 event handlers have tests
  - [x] Each handler has: happy path, empty input, error path
  - [x] All tests pass without external services
  - [x] Coverage report shows meaningful coverage
  - [x] No tests duplicate rcn-core coverage
