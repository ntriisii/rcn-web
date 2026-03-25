# Test rcn_web_interact.py and Storage Routes

## TL;DR

> **Quick Summary**: Create unit tests for `rcn_web_interact.py` CLI commands and storage/MCP route endpoints, remove unused functions from `rcn_interact.py`, and document SKILL.md discrepancies.

> **Deliverables**:
> - `tests/routes/test_storage_routes.py` - Tests for storage and MCP endpoints
> - Modified `~/bbtools/rcn_interact.py` - Removed unused functions
> - Verified SKILL.md documentation accuracy

> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Wave 1 → Wave 2 → Wave 3

---

## Context

### Original Request

User wants to verify that the script at `~/bbtools/rcn_interact.py` works correctly using tests, and ensure the documentation at `~/bbtools/skills/rcn-web/SKILL.md` is accurate.

### Interview Summary

**Key Discussions**:
- **Tool clarification**: User confirmed to test `rcn_web_interact.py` (modern MCP CLI), not `rcn_interact.py` (legacy)
- **Bug handling**: User wants to remove unused functions from `rcn_interact.py`: `del_server_data`, `modify_server_data`, `add_preview_server_data`
- **Test location**: Tests should go in `tests/routes/test_storage_routes.py`
- **SKILL.md**: Read as text file and verify accuracy

**Research Findings**:
- SKILL.md documents `describe-target` command but it's NOT implemented in `rcn_web_interact.py`
- SKILL.md documents `annotate` command but the script has `add_note` instead
- SKILL.md documents `add` command but it doesn't exist in the CLI
- All other commands (`preview`, `view`, `list_apps`, `delegate`, `schedule_fn`, `scan`, `fuzz`) are correctly documented

### Metis Review

**Identified Gaps** (addressed):
- Clarified which tool to test (rcn_web_interact.py, not rcn_interact.py)
- Clarified bug fix strategy (remove unused functions)
- Clarified test location (tests/routes/)
- Clarified SKILL.md handling (read as text, verify accuracy)

---

## Work Objectives

### Core Objective

Create comprehensive unit tests for `rcn_web_interact.py` CLI commands and the underlying storage/MCP route endpoints they use, while cleaning up unused code.

### Concrete Deliverables

1. **Test file**: `tests/routes/test_storage_routes.py` with tests for:
   - `/storage/getContent` endpoint (via `get_server_data`)
   - `/storage/addContent` endpoint (via `add_server_data`)
   - `/mcp/preview/generic` endpoint (via `preview` command)
   - `/mcp/view/generic` endpoint (via `view` command)
   - `/storage/addEntryAnnotation` endpoint (via `add_note` command)
   - `/mcp/action` endpoint (via `delegate` command)

2. **Modified file**: `~/bbtools/rcn_interact.py` with removed functions:
   - Remove `del_server_data()`
   - Remove `modify_server_data()`
   - Remove `add_preview_server_data()`

3. **Documentation note**: SKILL.md discrepancies documented in this plan

### Definition of Done

- [ ] All tests pass via `pytest tests/routes/test_storage_routes.py -v`
- [ ] Removed functions from `rcn_interact.py` verified
- [ ] SKILL.md discrepancies documented

### Must Have

- Tests for all CLI commands in `rcn_web_interact.py`
- Tests for storage route endpoints used by CLI
- Removal of unused functions from `rcn_interact.py`
- Mocked HTTP requests (no live server required)

### Must NOT Have (Guardrails)

- No testing of `describe-target` command (not implemented)
- No testing of `annotate` command (not implemented - use `add_note`)
- No integration tests requiring live server
- No refactoring of CLI scripts beyond removing unused functions

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision

- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD approach)
- **Framework**: pytest + unittest.mock
- **Test type**: Unit tests with mocked HTTP requests

### QA Policy

Every task includes agent-executed QA scenarios with evidence saved to `.sisyphus/evidence/`.

- **CLI Tests**: Mock `requests.post`, verify URL construction, payload structure, response handling
- **Route Tests**: Mock storage functions, verify endpoint behavior

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - can run in parallel):
├── Task 1: Create tests/routes/ directory structure [quick]
├── Task 2: Create test fixtures and helpers [quick]
└── Task 3: Remove unused functions from rcn_interact.py [quick]

Wave 2 (Core Tests - after Wave 1):
├── Task 4: Test /mcp/preview/generic endpoint [quick]
├── Task 5: Test /mcp/view/generic endpoint [quick]
├── Task 6: Test /storage/addEntryAnnotation endpoint [quick]
├── Task 7: Test /mcp/action endpoint [quick]
└── Task 8: Test /storage/getContent endpoint [quick]

Wave 3 (Integration Tests - after Wave 2):
├── Task 9: Test rcn_web_interact.py preview command [quick]
├── Task 10: Test rcn_web_interact.py view command [quick]
├── Task 11: Test rcn_web_interact.py add_note command [quick]
├── Task 12: Test rcn_web_interact.py delegate command [quick]
└── Task 13: Test rcn_web_interact.py scan/fuzz commands [quick]

Wave FINAL (Verification):
├── Task F1: Run all tests and verify pass [quick]
├── Task F2: Verify rcn_interact.py functions removed [quick]
└── Task F3: Git commit changes [quick]
```

Critical Path: Task 1-3 → Task 4-8 → Task 9-13 → F1-F3

---

## TODOs

### Wave 0: CLI Package Restructuring

- [ ] 0.1. Create rcn_web/cli/ package structure

**What to do**:
- Create `rcn_web/cli/` directory
- Create `rcn_web/cli/__init__.py`
- Create `rcn_web/cli/main.py` with Click group
- Create `rcn_web/cli/commands/` subdirectory
- Create command module files: `preview.py`, `annotate.py`, `delegate.py`, `scan.py`, `schedule.py`

**Must NOT do**:
- Do not modify existing `rcn_web` modules

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Directory and file scaffolding

**Parallelization**:
- **Can Run In Parallel**: NO - foundation for other tasks
- **Parallel Group**: Sequential (Wave 0)
- **Blocks**: All other tasks
- **Blocked By**: None

**References**:
- Pattern: `rcn_web/scanning/` - Package structure pattern

**Acceptance Criteria**:
- [ ] `rcn_web/cli/` directory exists
- [ ] `rcn_web/cli/__init__.py` exists
- [ ] `rcn_web/cli/main.py` has Click group defined

**QA Scenarios**:
```
Scenario: CLI package structure created
Tool: Bash
Steps:
  1. ls -la rcn_web/cli/
Expected Result: Directory with __init__.py, main.py, commands/
Evidence: .sisyphus/evidence/task-00.1-cli-structure.txt
```

**Commit**: NO (group with Wave 0)

---

- [ ] 0.2. Update pyproject.toml with CLI entry point

**What to do**:
- Add `[project.scripts]` section
- Add `rcn-web-interact = "rcn_web.cli.main:main"` entry point
- Add `click` to dependencies

**Recommended Agent Profile**:
- **Category**: `quick`

**References**:
- File: `pyproject.toml` - Current project config

**Acceptance Criteria**:
- [ ] `[project.scripts]` section exists
- [ ] `click` in dependencies
- [ ] Entry point points to `rcn_web.cli.main:main`

**Commit**: NO (group with Wave 0)

---

- [ ] 0.3. Implement Click CLI main entry point

**What to do**:
- Create `rcn_web/cli/main.py` with `@click.group()` 
- Add `--base-url` option with default `http://localhost:8023`
- Support `RCN_WEB_URL` environment variable
- Import and register all command groups

**Recommended Agent Profile**:
- **Category**: `quick`

**References**:
- Pattern: Click CLI with groups and context
- CLI: `~/bbtools/rcn_web_interact.py` - Current implementation to migrate

**Acceptance Criteria**:
- [ ] `rcn-web-interact --help` shows all commands
- [ ] `--base-url` option works
- [ ] `RCN_WEB_URL` env var works

**Commit**: YES (Wave 0 complete)
- Message: `feat: add installable CLI package with entry point`
- Files: `rcn_web/cli/`, `pyproject.toml`

---

### Wave 1: Foundation Tests

- [ ] 1. Create tests/routes/ directory structure

**What to do**:
- Create `tests/routes/` directory
- Create `tests/routes/__init__.py` (empty file for package)

**Must NOT do**:
- Do not modify existing test directories

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Simple file/directory creation

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2, 3)
- **Blocks**: Tasks 4-8
- **Blocked By**: None

**References**:
- Pattern: `tests/scanning/__init__.py` - Existing init file pattern
- Pattern: `tests/core/__init__.py` - Existing init file pattern

**Acceptance Criteria**:
- [ ] `tests/routes/` directory exists
- [ ] `tests/routes/__init__.py` exists

**QA Scenarios**:
```
Scenario: Directory structure created correctly
Tool: Bash
Steps:
  1. ls -la tests/routes/
Expected Result: Directory exists with __init__.py
Evidence: .sisyphus/evidence/task-01-dir-structure.txt
```

**Commit**: NO (group with Task 3)

---

- [ ] 2. Create test fixtures and helpers

**What to do**:
- Create shared fixtures for mocking HTTP requests
- Create helper function to mock `requests.post`
- Create sample response data fixtures

**Must NOT do**:
- Do not modify existing conftest.py

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Simple fixture creation

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 3)
- **Blocks**: Tasks 4-8
- **Blocked By**: None

**References**:
- Pattern: `tests/conftest.py` - Existing fixture patterns
- Pattern: `tests/scanning/test_mcp_scanners.py:create_mock_context_manager` - Mock helper pattern

**Acceptance Criteria**:
- [ ] `mock_requests_response` fixture created
- [ ] `mock_successful_response` helper created

**QA Scenarios**:
```
Scenario: Fixtures can be imported
Tool: Bash
Steps:
  1. python -c "from tests.routes.test_storage_routes import *"
Expected Result: No import errors
Evidence: .sisyphus/evidence/task-02-fixtures.txt
```

**Commit**: NO (group with Task 3)

---

- [ ] 3. Remove unused functions from rcn_interact.py

**What to do**:
- Remove `del_server_data()` function (lines 111-119)
- Remove `modify_server_data()` function (lines 122-134)
- Remove `add_preview_server_data()` function (lines 137-149)
- Remove corresponding method cases from `main()` function

**Must NOT do**:
- Do not remove `get_server_data` or `add_server_data`
- Do not remove `parse_json`, `read_pipe_content`, `read_input_file`

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Simple code removal

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 2)
- **Blocks**: None
- **Blocked By**: None

**References**:
- File: `~/bbtools/rcn_interact.py` - Lines 51-60 contain the method dispatch to update
- File: `~/bbtools/rcn_interact.py` - Lines 111-149 contain functions to remove

**Acceptance Criteria**:
- [ ] `del_server_data` function removed
- [ ] `modify_server_data` function removed
- [ ] `add_preview_server_data` function removed
- [ ] Method cases removed from `main()`
- [ ] Script still runs without errors for `add` and `get` methods

**QA Scenarios**:
```
Scenario: Functions removed correctly
Tool: Bash
Steps:
  1. grep -c "def del_server_data" ~/bbtools/rcn_interact.py
  2. grep -c "def modify_server_data" ~/bbtools/rcn_interact.py
  3. grep -c "def add_preview_server_data" ~/bbtools/rcn_interact.py
Expected Result: All return 0 (not found)
Evidence: .sisyphus/evidence/task-03-removed.txt
```

**Commit**: YES (group with Tasks 1, 2)
- Message: `test: setup routes test directory and remove unused functions from rcn_interact.py`
- Files: `tests/routes/__init__.py`, `tests/routes/test_storage_routes.py` (fixtures), `~/bbtools/rcn_interact.py`

---

- [ ] 4. Test /mcp/preview/generic endpoint

**What to do**:
- Create test class `TestMcppreviewGeneric`
- Test happy path: storage preview returned
- Test with `sql_filter` parameter
- Test with `parent_id` (app_id) parameter
- Test error handling: connection error

**Must NOT do**:
- Do not test actual server responses (mock only)

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Standard endpoint testing

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 5-8)
- **Blocks**: Task 9
- **Blocked By**: Tasks 1-2

**References**:
- API: `rcn_web/routes/mcp_api.py:router` - MCP router endpoints
- Pattern: `tests/scanning/test_mcp_scanners.py` - Test structure pattern

**Acceptance Criteria**:
- [ ] Test for successful preview response
- [ ] Test with sql_filter
- [ ] Test with parent_id
- [ ] Test connection error handling

**QA Scenarios**:
```
Scenario: Preview endpoint returns storage metadata
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestMcppreviewGeneric -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-04-preview.txt
```

**Commit**: NO (group with Task 8)

---

- [ ] 5. Test /mcp/view/generic endpoint

**What to do**:
- Create test class `TestMcpViewGeneric`
- Test happy path: entries returned with pagination
- Test with `sql_filter` parameter
- Test with `page` and `limit` parameters
- Test with `parent_id` parameter
- Test error handling: connection error

**Must NOT do**:
- Do not test actual server responses

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Standard endpoint testing

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4, 6-8)
- **Blocks**: Task 10
- **Blocked By**: Tasks 1-2

**References**:
- API: `rcn_web/routes/mcp_api.py:router` - MCP router endpoints

**Acceptance Criteria**:
- [ ] Test for successful view response
- [ ] Test pagination parameters
- [ ] Test with parent_id
- [ ] Test connection error handling

**QA Scenarios**:
```
Scenario: View endpoint returns paginated entries
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestMcpViewGeneric -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-05-view.txt
```

**Commit**: NO (group with Task 8)

---

- [ ] 6. Test /storage/addEntryAnnotation endpoint

**What to do**:
- Create test class `TestAddEntryAnnotation`
- Test happy path: annotation added successfully
- Test with multiple `app_name` values
- Test with `app_id` instead of `app_name`
- Test with different `storage_name` values
- Test with `web-apps` storage (application-level annotation)
- Test error handling: app not found

**Must NOT do**:
- Do not test actual database writes

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Standard endpoint testing

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4-5, 7-8)
- **Blocks**: Task 11
- **Blocked By**: Tasks 1-2

**References**:
- API: `rcn_web/routes/storage.py:80-136` - addEntryAnnotation endpoint
- Pattern: `tests/scanning/test_mcp_scanners.py` - Test structure

**Acceptance Criteria**:
- [ ] Test for successful annotation
- [ ] Test with multiple apps
- [ ] Test with app_id
- [ ] Test with web-apps storage
- [ ] Test error handling

**QA Scenarios**:
```
Scenario: Annotation endpoint adds entry correctly
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestAddEntryAnnotation -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-06-annotation.txt
```

**Commit**: NO (group with Task 8)

---

- [ ] 7. Test /mcp/action endpoint

**What to do**:
- Create test class `TestMcpAction`
- Test happy path: action executed successfully
- Test `delegate_to_acp` action with valid parameters
- Test error handling: invalid action
- Test error handling: connection error

**Must NOT do**:
- Do not test actual agent delegation

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Standard endpoint testing

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4-6, 8)
- **Blocks**: Task 12
- **Blocked By**: Tasks 1-2

**References**:
- API: `rcn_web/routes/mcp_api.py` - MCP action handler

**Acceptance Criteria**:
- [ ] Test for successful action
- [ ] Test delegate_to_acp action
- [ ] Test invalid action handling
- [ ] Test connection error handling

**QA Scenarios**:
```
Scenario: Action endpoint delegates correctly
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestMcpAction -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-07-action.txt
```

**Commit**: NO (group with Task 8)

---

- [ ] 8. Test /storage/getContent endpoint

**What to do**:
- Create test class `TestGetContent`
- Test happy path: storage data returned
- Test with `query-expression` filter (compiled code)
- Test empty result
- Test error handling

**Must NOT do**:
- Do not test actual storage access

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: Standard endpoint testing

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4-7)
- **Blocks**: None
- **Blocked By**: Tasks 1-2

**References**:
- API: `rcn_web/routes/storage.py:18-26` - getContent endpoint

**Acceptance Criteria**:
- [ ] Test for successful response
- [ ] Test with filter expression
- [ ] Test empty result
- [ ] Test error handling

**QA Scenarios**:
```
Scenario: GetContent endpoint returns data correctly
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestGetContent -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-08-getcontent.txt
```

**Commit**: YES (group with Tasks 4-7)
- Message: `test: add unit tests for storage and MCP route endpoints`
- Files: `tests/routes/test_storage_routes.py`

---

- [ ] 9. Test rcn_web_interact.py preview command

**What to do**:
- Create test class `TestRcnWebInteractPreview`
- Test CLI invocation with `--storage` parameter
- Test CLI invocation with `--app-id` parameter
- Test CLI invocation with `--filter` parameter
- Test error handling: missing required parameter
- Mock `requests.post` and verify URL/payload

**Must NOT do**:
- Do not test actual HTTP calls

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: CLI testing with mocks

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Tasks 10-13)
- **Blocks**: None
- **Blocked By**: Tasks 1-4

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:28-44` - preview command
- Pattern: Use `click.testing.CliRunner` for CLI testing

**Acceptance Criteria**:
- [ ] Test with storage parameter
- [ ] Test with app-id parameter
- [ ] Test with filter parameter
- [ ] Test missing parameter error

**QA Scenarios**:
```
Scenario: Preview command constructs correct request
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractPreview -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-09-cli-preview.txt
```

**Commit**: NO (group with Task 13)

---

- [ ] 10. Test rcn_web_interact.py view command

**What to do**:
- Create test class `TestRcnWebInteractView`
- Test CLI invocation with `--storage` parameter
- Test CLI invocation with `--page` and `--limit` parameters
- Test CLI invocation with `--filter` parameter
- Test error handling: missing required parameter

**Must NOT do**:
- Do not test actual HTTP calls

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: CLI testing with mocks

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Tasks 9, 11-13)
- **Blocks**: None
- **Blocked By**: Tasks 1-5

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:46-64` - view command

**Acceptance Criteria**:
- [ ] Test with storage parameter
- [ ] Test with pagination
- [ ] Test with filter
- [ ] Test missing parameter error

**QA Scenarios**:
```
Scenario: View command constructs correct request
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractView -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-10-cli-view.txt
```

**Commit**: NO (group with Task 13)

---

- [ ] 11. Test rcn_web_interact.py add_note command

**What to do**:
- Create test class `TestRcnWebInteractAddNote`
- Test CLI invocation with all required parameters
- Test with default `--storage` and `--category`
- Test error handling: missing required parameter

**Must NOT do**:
- Do not test actual annotation creation

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: CLI testing with mocks

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Tasks 9-10, 12-13)
- **Blocks**: None
- **Blocked By**: Tasks 1-6

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:92-116` - add_note command

**Acceptance Criteria**:
- [ ] Test with all parameters
- [ ] Test with defaults
- [ ] Test missing parameter error

**QA Scenarios**:
```
Scenario: Add_note command constructs correct request
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractAddNote -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-11-cli-addnote.txt
```

**Commit**: NO (group with Task 13)

---

- [ ] 12. Test rcn_web_interact.py delegate command

**What to do**:
- Create test class `TestRcnWebInteractDelegate`
- Test CLI invocation with all required parameters
- Test with optional `--ids` parameter
- Test error handling: missing required parameter

**Must NOT do**:
- Do not test actual delegation

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: CLI testing with mocks

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Tasks 9-11, 13)
- **Blocks**: None
- **Blocked By**: Tasks 1-7

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:118-140` - delegate command

**Acceptance Criteria**:
- [ ] Test with all parameters
- [ ] Test with ids parameter
- [ ] Test missing parameter error

**QA Scenarios**:
```
Scenario: Delegate command constructs correct request
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractDelegate -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-12-cli-delegate.txt
```

**Commit**: NO (group with Task 13)

---

- [ ] 13. Test rcn_web_interact.py scan/fuzz commands

**What to do**:
- Create test class `TestRcnWebInteractScanFuzz`
- Test `scan` command with `--app` and `--xml`
- Test `fuzz` command with `--app` and `--xml`
- Test that source_id is generated correctly
- Test error handling: missing parameters

**Must NOT do**:
- Do not test actual scanning/fuzzing

**Recommended Agent Profile**:
- **Category**: `quick`
- Reason: CLI testing with mocks

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Tasks 9-12)
- **Blocks**: None
- **Blocked By**: Tasks 1-8

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:208-227` - scan command
- CLI: `~/bbtools/rcn_web_interact.py:229-248` - fuzz command

**Acceptance Criteria**:
- [ ] Test scan command
- [ ] Test fuzz command
- [ ] Test source_id generation
- [ ] Test missing parameter error

**QA Scenarios**:
```
Scenario: Scan and fuzz commands construct correct requests
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractScanFuzz -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-13-cli-scanfuzz.txt
```

**Commit**: YES (group with Tasks 9-12)
- Message: `test: add CLI integration tests for rcn_web_interact commands`
- Files: `tests/routes/test_storage_routes.py`

---

- [ ] 14. Implement describe-target command

**What to do**:
- Add `describe_target` command to CLI
- Call `/apps/preview_apps` endpoint with target identifier
- Display target metadata and annotations in formatted output
- Display storage entry counts using `/mcp/preview/generic`

**Must NOT do**:
- Do not add new server endpoint (use existing `/apps/preview_apps`)

**Recommended Agent Profile**:
- **Category**: `quick`

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 4 (with Tasks 15-17)
- **Blocked By**: Wave 3

**References**:
- Endpoint: `rcn_web/routes/applications.py:206` - `preview_apps` endpoint
- SKILL.md: Lines 47-57 - `describe-target` command specification

**Acceptance Criteria**:
- [ ] `rcn-web-interact describe-target` displays target metadata
- [ ] Shows available storages with entry counts
- [ ] Handles missing target gracefully

**QA Scenarios**:
```
Scenario: Describe-target shows target info
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractDescribeTarget -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-14-describe-target.txt
```

**Commit**: NO (group with Wave 4)

---

- [ ] 15. Add annotate command as alias to add_note

**What to do**:
- Add `annotate` command that calls `add_note` functionality
- Ensure both `annotate` and `add_note` work identically
- Update SKILL.md to show both commands are valid

**Recommended Agent Profile**:
- **Category**: `quick`

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 4 (with Tasks 14, 16-17)
- **Blocked By**: Wave 3

**References**:
- CLI: `~/bbtools/rcn_web_interact.py:92-116` - `add_note` implementation
- SKILL.md: Lines 119-156 - `annotate` command specification

**Acceptance Criteria**:
- [ ] `rcn-web-interact annotate` works
- [ ] `rcn-web-interact add-note` works (backward compatible)
- [ ] Both produce identical results

**QA Scenarios**:
```
Scenario: Annotate command works as alias
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractAnnotate -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-15-annotate.txt
```

**Commit**: NO (group with Wave 4)

---

- [ ] 16. Implement add command for adding data to storage

**What to do**:
- Add `add` command to CLI
- Accept `--storage`, `--app`, `--data` parameters
- Call `/storage/addContent` endpoint
- Validate JSON data format

**Recommended Agent Profile**:
- **Category**: `quick`

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 4 (with Tasks 14-15, 17)
- **Blocked By**: Wave 3

**References**:
- SKILL.md: Lines 211-221 - `add` command specification
- Endpoint: `rcn_web/routes/storage.py:34-47` - `addContent` endpoint

**Acceptance Criteria**:
- [ ] `rcn-web-interact add --storage "web-apps::js-links" --app "example.com" --data '{...}'` works
- [ ] Validates JSON format
- [ ] Handles errors gracefully

**QA Scenarios**:
```
Scenario: Add command adds data to storage
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py::TestRcnWebInteractAdd -v
Expected Result: All tests pass
Evidence: .sisyphus/evidence/task-16-add.txt
```

**Commit**: NO (group with Wave 4)

---

- [ ] 17. Write tests for new CLI commands

**What to do**:
- Write tests for `describe-target` command
- Write tests for `annotate` command (alias verification)
- Write tests for `add` command
- Mock HTTP requests, verify correct endpoints called

**Recommended Agent Profile**:
- **Category**: `quick`

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 4 (with Tasks 14-16)
- **Blocked By**: Wave 3

**Acceptance Criteria**:
- [ ] All new command tests pass
- [ ] Tests verify correct endpoint URLs
- [ ] Tests verify payload structure

**Commit**: YES (Wave 4 complete)
- Message: `feat: add describe-target, annotate, and add CLI commands with tests`
- Files: `rcn_web/cli/`, `tests/routes/test_storage_routes.py`

---

## Final Verification Wave

- [ ] F1. Run all tests and verify pass

**What to do**:
- Run `pytest tests/routes/test_storage_routes.py -v`
- Verify all tests pass
- Capture output as evidence

**Recommended Agent Profile**:
- **Category**: `quick`

**QA Scenarios**:
```
Scenario: All tests pass
Tool: Bash
Steps:
  1. pytest tests/routes/test_storage_routes.py -v
Expected Result: All tests pass, 0 failures
Evidence: .sisyphus/evidence/final-test-run.txt
```

---

- [ ] F2. Verify rcn_interact.py functions removed

**What to do**:
- Verify `del_server_data` not in file
- Verify `modify_server_data` not in file
- Verify `add_preview_server_data` not in file

**Recommended Agent Profile**:
- **Category**: `quick`

**QA Scenarios**:
```
Scenario: Functions removed
Tool: Bash
Steps:
  1. grep -E "def (del_server_data|modify_server_data|add_preview_server_data)" ~/bbtools/rcn_interact.py
Expected Result: Empty output (no matches)
Evidence: .sisyphus/evidence/final-removal.txt
```

---

- [ ] F3. Git commit changes

**What to do**:
- Commit all test files
- Commit rcn_interact.py changes
- Do not verify commit, do not run git status

**Recommended Agent Profile**:
- **Category**: `quick`

**Commit**:
- Message: `test: complete testing for rcn_web_interact and cleanup rcn_interact`
- Files: All changes

---

## Commit Strategy

1. `test: setup routes test directory and remove unused functions from rcn_interact.py` (Wave 1)
2. `test: add unit tests for storage and MCP route endpoints` (Wave 2)
3. `test: add CLI integration tests for rcn_web_interact commands` (Wave 3)
4. `test: complete testing for rcn_web_interact and cleanup rcn_interact` (Final)

---

## Success Criteria

### Verification Commands

```bash
# Run all tests
pytest tests/routes/test_storage_routes.py -v

# Verify functions removed
grep -E "def (del_server_data|modify_server_data|add_preview_server_data)" ~/bbtools/rcn_interact.py
# Expected: Empty output
```

### Final Checklist

- [ ] All route endpoint tests pass
- [ ] All CLI command tests pass
- [ ] Unused functions removed from rcn_interact.py
- [ ] SKILL.md discrepancies documented

---

## SKILL.md Documentation Discrepancies

| Command | SKILL.md Status | Actual Status | Action |
|---------|-----------------|---------------|--------|
| `describe-target` | Documented | **NOT IMPLEMENTED** | **IMPLEMENT** - Use `/apps/preview_apps` endpoint |
| `preview` | Documented | Implemented ✓ | No change |
| `view` | Documented | Implemented ✓ | No change |
| `list_apps` | Documented | Implemented ✓ | No change |
| `annotate` | Documented | CLI has `add_note` | **ADD ALIAS** - Add `annotate` as alias to `add_note` |
| `add` | Documented | **NOT IMPLEMENTED** | **IMPLEMENT** - Add data to storage |
| `delegate` | Documented | Implemented ✓ | No change |
| `schedule_fn` | Documented | Implemented ✓ | No change |
| `scan` | Documented | Implemented ✓ | No change |
| `fuzz` | Documented | Implemented ✓ | No change |

---

## CLI as Installable Package

### Architecture Change

**Current State**: `rcn_web_interact.py` is a standalone script in `~/bbtools/`

**Target State**: CLI becomes part of `rcn_web` package:

```
rcn_web/
├── cli/
│   ├── __init__.py
│   ├── main.py          # Entry point with Click group
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── preview.py   # preview, view commands
│   │   ├── annotate.py  # add_note, annotate commands
│   │   ├── delegate.py  # delegate command
│   │   ├── scan.py      # scan, fuzz commands
│   │   └── schedule.py  # schedule_fn command
│   └── utils.py         # Shared utilities
```

### pyproject.toml Entry Point

```toml
[project.scripts]
rcn-web-interact = "rcn_web.cli.main:main"
```

### Testing Strategy

1. **Unit Tests**: Use `click.testing.CliRunner` to test command parsing
2. **Integration Tests**: Start FastAPI server, test CLI against live endpoints
3. **Configurable URL**: `RCN_WEB_URL` env var or `--base-url` option
