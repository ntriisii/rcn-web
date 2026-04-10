# JS Viewer Flow ID Request Refactoring

## TL;DR
> **Quick Summary**: Refactor JS viewers (js-flows, js-links) to request flow content directly from the proxy using `ewp--get-entry`, matching the pattern used by flows and URLs viewers.
>
> **Deliverables**:
> - Updated Python viewer configs in `js.py`
> - New Elisp navigate functions in web-recon-viewer
>
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - sequential (2 tasks, different codebases)
> **Critical Path**: Task 1 → Task 2

---

## Context

### Original Request
User requested: "make the js viewers behave like flows and urls, they have to request the flow ID from the proxy, the same way links and flows do, make sure to change this in the frontend as well."

### Interview Summary
**Key Discussions**:
- Current JS viewers use backend endpoint `/apps/js/contentByFlowId` for content retrieval
- Flow/URL viewers use proxy directly via `ewp--get-entry` calling `GET /getFlow/<id>`
- Need to align JS viewers with the proxy-direct pattern

**Research Findings**:
- Flow viewers: `recon-flows.el:19-31` - `rcn-view-flow-navigate-fn` extracts flow-id and calls `ewp--get-entry`
- URL viewers: `url-view.el:89-101` - `rcn-view-url-navigate-fn` uses same pattern
- Proxy endpoint: `ewp--get-entry` requests `GET http://ewp-server-name/getFlow/<flow_id>`
- JS viewers: `js.py:66,157` - Uses `"get-content-url": "/apps/js/contentByFlowId"` (backend, not proxy)

### Gap Analysis (Self-Identified)
**Questions I should have asked**:
1. Should we remove the backend endpoint `/apps/js/contentByFlowId` or keep it for other uses?
2. Are there other callers of `/apps/js/contentByFlowId` that would break?

**Guardrails Applied**:
- Only modify JS viewer navigate functions - don't change flow/URL viewers
- Keep `flow-id` in `additional_keys` (already present)
- Don't modify the proxy server code

---

## Work Objectives

### Core Objective
Make JS viewers (js-flows and js-links) request flow content directly from the proxy using `ewp--get-entry`, matching the pattern used by flows and URLs viewers.

### Concrete Deliverables
1. Python: Update `rcn_web/viewers/emacs/js.py` viewer configs
2. Elisp: Create `rcn-view-js-flow-navigate-fn` in web-recon-viewer
3. Elisp: Create `rcn-view-js-link-navigate-fn` in web-recon-viewer

### Definition of Done
- [ ] JS flows viewer uses proxy for content retrieval (verified in Emacs)
- [ ] JS links viewer uses proxy for content retrieval (verified in Emacs)
- [ ] Existing flow/URL viewers continue working unchanged

### Must Have
- JS viewers must use `ewp--get-entry` to request flow data from proxy
- Must preserve `flow-id` column in tabulated entries
- Must maintain current key-bindings (gtN, gtb, etc.)

### Must NOT Have (Guardrails)
- Do NOT modify flow viewer or URL viewer code
- Do NOT change the proxy server implementation
- Do NOT remove `flow-id` from `additional_keys`

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (no test framework for Elisp/Emacs integration)
- **Automated tests**: NO
- **Agent-Executed QA**: YES - Manual verification in Emacs

### QA Policy
Every task includes agent-executed QA scenarios using interactive Emacs verification.

---

## Execution Strategy

### Parallel Execution Waves
```
Wave 1 (Sequential - different codebases):
├── Task 1: Python viewer config updates [quick]
└── Task 2: Elisp navigate functions [quick]

Critical Path: Task 1 → Task 2
```

### Dependency Matrix
- **Task 1**: — (can start immediately)
- **Task 2**: Task 1 (needs updated config to reference correct navigate-fn)

### Agent Dispatch Summary
- **Wave 1**: 2 tasks → `quick` category

---

## TODOs

- [x] 1. Update Python JS Viewer Configs

 **What to do**:
 - Remove `"get-content-url"` from `web-apps::js-flows` view-store (line 66)
 - Remove `"get-content-url"` from `web-apps::js-links` view-store (line 157)
 - Update `"navigate-fn"` from `"rcn-view-flow-navigate-fn"` to `"rcn-view-js-flow-navigate-fn"` for js-flows (line 28)
 - Update `"navigate-fn"` from `"rcn-view-url-navigate-fn"` to `"rcn-view-js-link-navigate-fn"` for js-links (line 117)
 - Keep `flow-id` in `additional_keys` (lines 88, 187) - no change needed

 **Must NOT do**:
 - Do NOT change flow-id column position (it's already correct)
 - Do NOT modify the attrs or tabulated-format

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - Reason: Single file changes, straightforward config updates
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: NO
 - **Parallel Group**: Sequential
 - **Blocks**: Task 2
 - **Blocked By**: None

 **References**:
 - `rcn_web/viewers/emacs/js.py:60-70` - js-flows view-store config
 - `rcn_web/viewers/emacs/js.py:151-161` - js-links view-store config
 - `rcn_web/viewers/emacs/flows.py:75-89` - Reference for flow-id pattern
 - `/home/ahmed/programming-projects/elisp/web-recon-viewer/recon-flows.el:19-31` - Reference navigate function pattern

 **Acceptance Criteria**:
 - [ ] `"get-content-url"` removed from both view-store configs
 - [ ] `"navigate-fn"` updated to new function names
 - [ ] `flow-id` still present in `additional_keys`

 **QA Scenarios**:
 ```
 Scenario: Verify viewer config changes
 Tool: Bash (grep)
 Steps:
   1. grep -n "get-content-url" rcn_web/viewers/emacs/js.py
   2. Verify no matches (or only in comments)
 Expected Result: No "get-content-url" in js.py view-store configs
 Evidence: .sisyphus/evidence/task-1-config-check.txt

 Scenario: Verify navigate-fn updated
 Tool: Bash (grep)
 Steps:
   1. grep -n "navigate-fn" rcn_web/viewers/emacs/js.py
   2. Verify "rcn-view-js-flow-navigate-fn" and "rcn-view-js-link-navigate-fn" present
 Expected Result: New navigate function names in config
 Evidence: .sisyphus/evidence/task-1-navigate-fn.txt
 ```

 **Commit**: YES
 - Message: `refactor(viewers): update js viewer configs for proxy flow requests`
 - Files: `rcn_web/viewers/emacs/js.py`

---

- [x] 2. Create Elisp Navigate Functions for JS Viewers

 **What to do**:
 - Create `rcn-view-js-flow-navigate-fn` in web-recon-viewer (similar to `rcn-view-flow-navigate-fn`)
 - Create `rcn-view-js-link-navigate-fn` in web-recon-viewer (similar to `rcn-view-url-navigate-fn`)
 - Both functions should:
   1. Get view-store name from buffer local variable
   2. Extract flow-id from tabulated entry (column position differs: js-flows uses column 2, js-links uses column 3)
   3. Call `ewp--get-entry flow-id` to get full flow data from proxy
   4. Populate request and response buffers using `ewp-history--make-request-buffer` and `ewp-history--make-response-buffer`

 **Must NOT do**:
 - Do NOT modify existing flow or URL navigate functions
 - Do NOT change ewp--get-entry implementation

 **Recommended Agent Profile**:
 - **Category**: `quick`
 - Reason: Small Elisp functions following established pattern
 - **Skills**: []

 **Parallelization**:
 - **Can Run In Parallel**: NO
 - **Parallel Group**: Sequential
 - **Blocks**: None
 - **Blocked By**: Task 1

 **References**:
 - `/home/ahmed/programming-projects/elisp/web-recon-viewer/recon-flows.el:19-31` - Reference: `rcn-view-flow-navigate-fn` pattern
 - `/home/ahmed/programming-projects/elisp/web-recon-viewer/url-view.el:89-101` - Reference: `rcn-view-url-navigate-fn` pattern
 - `/home/ahmed/programming-projects/elisp/emacs-web-proxy/ewp-history.el:756-768` - Reference: `ewp--get-entry` function
 - `rcn_web/viewers/emacs/js.py:82-89` - js-flows attrs: flow-id is column 2 (after path)
 - `rcn_web/viewers/emacs/js.py:173-180` - js-links attrs: flow-id is column 3 (after id and path)

 **Acceptance Criteria**:
 - [ ] `rcn-view-js-flow-navigate-fn` function defined in Elisp
 - [ ] `rcn-view-js-link-navigate-fn` function defined in Elisp
 - [ ] Both functions call `ewp--get-entry` with correct flow-id extraction

 **QA Scenarios**:
 ```
 Scenario: Verify Elisp functions defined
 Tool: Bash (grep)
 Steps:
   1. grep -n "defun rcn-view-js-flow-navigate-fn" /home/ahmed/programming-projects/elisp/web-recon-viewer/*.el
   2. grep -n "defun rcn-view-js-link-navigate-fn" /home/ahmed/programming-projects/elisp/web-recon-viewer/*.el
 Expected Result: Both functions found in Elisp files
 Evidence: .sisyphus/evidence/task-2-functions.txt

 Scenario: Verify ewp--get-entry usage
 Tool: Bash (grep)
 Steps:
   1. grep -A5 "rcn-view-js-flow-navigate-fn" /home/ahmed/programming-projects/elisp/web-recon-viewer/*.el
   2. Verify "ewp--get-entry" is called in function body
 Expected Result: ewp--get-entry called with flow-id
 Evidence: .sisyphus/evidence/task-2-ewp-call.txt
 ```

 **Commit**: YES
 - Message: `feat(elisp): add js viewer navigate functions for proxy flow requests`
 - Files: `/home/ahmed/programming-projects/elisp/web-recon-viewer/recon-flows.el` (or new file)

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
 Verify both tasks completed: Python config updated, Elisp functions created. Check evidence files exist.

- [x] F2. **Code Quality Review** — `unspecified-high`
 Review Python changes for syntax errors. Review Elisp for correct function definitions.

- [x] F3. **Real Manual QA** — `unspecified-high`
 Load changed files in Emacs, navigate JS flows and JS links, verify content appears.

- [x] F4. **Scope Fidelity Check** — `deep`
 Verify only JS viewer code changed, flow/URL viewers untouched.

---

## Commit Strategy

- **Task 1**: `refactor(viewers): update js viewer configs for proxy flow requests` — `rcn_web/viewers/emacs/js.py`
- **Task 2**: `feat(elisp): add js viewer navigate functions for proxy flow requests` — `web-recon-viewer/recon-flows.el`

---

## Success Criteria

### Verification Commands
```bash
# Verify Python changes
grep -n "navigate-fn" rcn_web/viewers/emacs/js.py
# Expected: New function names "rcn-view-js-flow-navigate-fn" and "rcn-view-js-link-navigate-fn"

# Verify Elisp functions exist
grep -n "defun rcn-view-js" /home/ahmed/programming-projects/elisp/web-recon-viewer/*.el
# Expected: Two function definitions
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] JS viewers work in Emacs
- [ ] Flow/URL viewers unchanged
