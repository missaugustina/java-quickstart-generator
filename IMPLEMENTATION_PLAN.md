# Java Quickstart Generator: Python Implementation Plan

## Purpose

This plan divides implementation into small, ordered tasks that can be given to an LLM one at a time in the same conversation. Each task has a narrow responsibility so the agent can focus, test its work, and stop before moving to the next concern.

The project is a simple proof of concept. It will use the Codex SDK to generate one Java Quickstart module through a chain of focused prompts. Every prompt in a module will run in the same Codex thread so later parts can build on earlier parts.

## Territory Map

```text
Guide specification + ordered module prompt files
                        |
                        v
               GuidePromptBuilder
                        |
                        v
             Codex thread, turn 1..n
                        |
                        v
                MarkdownWriter
                        |
                        v
              tracked Markdown drafts
```

The logical layers are:

1. **Models** hold data.
2. **Roles** define required behavior through Python protocols.
3. **Adapters** connect the program to prompt formatting, the Codex SDK, and the filesystem.
4. **Workflow** coordinates the roles without knowing their implementation details.
5. **CLI** accepts user input, assembles dependencies, runs the workflow, and reports results.
6. **Tests** verify each layer offline.

## Target Data Model

The intended data objects are:

- `GeneratorConfig`
  - `guide_spec`: path to the main guide specification
  - `prompts_directory`: root containing module prompt files
  - `drafts_directory`: root for generated Markdown drafts
- `ModulePart`
  - `module_id`: stable module identifier
  - `prompt_path`: path to one part prompt
  - `title`: human-readable part title
- `GenerationRequest`
  - `part`: the current `ModulePart`
  - `instruction`: prompt text already read from disk
  - `thread_id`: existing Codex thread ID, or `None` for the first turn
- `AgentResponse`
  - `content`: generated Markdown content
  - `thread_id`: Codex thread used for the response
- `GenerationOutcome`
  - `part`: the completed `ModulePart`
  - `artifact_path`: path to its written draft
  - `thread_id`: Codex thread used for the part

## Prompting Rules for Every Implementation Task

Include these instructions whenever asking an agent to implement one task:

```text
Work only on the stated task.
Read the existing inline pseudocode before editing.
Replace only the pseudocode covered by this task.
Preserve the role-oriented architecture: passive data models, narrow Protocols,
small adapters, and workflow functions that coordinate those roles.
Do not introduce frameworks, a database, retries, asynchronous execution,
plugins, or other architecture not required by the task.
Manage all dependencies through uv.
Do not make a live Codex request unless this task explicitly authorizes it.
Run Ruff formatting and linting, Pyright, and the relevant offline tests.
At the end, report:
1. files changed;
2. behavior implemented;
3. verification results;
4. assumptions made; and
5. pseudocode intentionally left for later tasks.
Then stop.
```

## Ordered Implementation Tasks

### Task 0: Inspect the Current Project and Codex SDK

**Mode:** Read only

**Focus:** Establish facts before changing code.

**Instructions:**

- Read the Python stubs and their inline pseudocode.
- Read `pyproject.toml`, `README.md`, `.gitignore`, and the existing tests.
- Inspect the installed `openai-codex` package or its official documentation.
- Confirm the actual synchronous APIs for:
  - constructing and closing `Codex`;
  - starting a thread;
  - resuming a thread;
  - running a prompt;
  - obtaining `final_response`;
  - obtaining the thread ID; and
  - selecting `Sandbox.read_only`.
- Identify any mismatch between the pseudocode and the installed SDK.
- Do not edit files.

**Deliverable:** A short factual implementation memo that names the relevant SDK types, methods, and signatures.

**Acceptance criteria:**

- No files are changed.
- Claims about the SDK are based on the installed package or official documentation.
- Uncertainty is identified instead of guessed.

---

### Task 1: Implement the Data Models

**File:** `src/java_quickstart_generator/models.py`

**Focus:** Data shape only.

**Instructions:**

- Implement the target data model described above.
- Use typed dataclasses with `frozen=True` and `slots=True` unless an inspected requirement makes either inappropriate.
- Keep models passive: no SDK calls, file reads, prompt construction, or workflow behavior.
- Use `pathlib.Path` for filesystem paths.
- Add concise docstrings only where they clarify purpose.

**Acceptance criteria:**

- All five model types exist with explicit types.
- Models contain data, not operational behavior.
- Construction and immutability can be checked by tests or type checking.
- No new dependency is added.

---

### Task 2: Align the Behavioral Roles

**File:** `src/java_quickstart_generator/roles.py`

**Focus:** Interfaces only.

**Instructions:**

- Define or revise the narrow protocols:
  - `BuildsPrompt`
  - `RunsAgent`
  - `WritesArtifact`
- Make each method accept and return the models required by the workflow.
- Keep the protocols structural and implementation-neutral.
- Do not add base classes, registries, dependency-injection frameworks, or adapter logic.

**Acceptance criteria:**

- Each protocol expresses one behavior.
- The protocols do not import or expose Codex SDK classes.
- Filesystem details are absent except for model-level `Path` values.
- Pyright accepts intended structural implementations.

---

### Task 3: Implement the Single-Part Workflow

**File:** `src/java_quickstart_generator/workflow.py`

**Focus:** Orchestrate one prompt part.

**Instructions:**

- Implement `generate_part()`.
- Have the workflow:
  1. accept a prepared `GenerationRequest` and the three role dependencies;
  2. ask the prompt builder to create the final agent prompt;
  3. ask the agent runner to execute it;
  4. reject an empty response;
  5. ask the writer to save the content; and
  6. return `GenerationOutcome`.
- Do not read the part prompt from disk here if it is already present in `GenerationRequest.instruction`.
- Do not include SDK or concrete filesystem code.

**Acceptance criteria:**

- The function depends on protocols, not concrete adapters.
- Calls occur in the required order.
- The returned outcome contains the part, path, and thread ID.
- Empty agent output is rejected before the writer is called.

---

### Task 4: Test the Single-Part Workflow

**File:** `tests/test_workflow.py`

**Focus:** Test `generate_part()` with hand-written fakes.

**Instructions:**

- Add small fake implementations for the three protocols.
- Test the successful call sequence and returned outcome.
- Test first-turn behavior with no incoming thread ID.
- Test resumed behavior with an incoming thread ID.
- Test that empty agent content fails and is not written.
- Do not use mocks that depend on implementation internals.
- Do not call the Codex service.

**Acceptance criteria:**

- Tests prove the workflow’s observable behavior.
- No network access or credentials are required.
- Failures clearly identify which contract was violated.

---

### Task 5: Implement the Module-Chain Workflow

**File:** `src/java_quickstart_generator/workflow.py`

**Focus:** Generate every part of one module in one Codex thread.

**Instructions:**

- Implement `generate_module()` separately from `generate_part()`.
- Discover only regular Markdown files in the requested module directory.
- Sort prompt files deterministically by filename.
- Reject a missing module directory or a module with no prompt files.
- Read each prompt file once as UTF-8.
- Reject an empty part prompt.
- Pass the first request with `thread_id=None`.
- Carry the returned thread ID into every later request.
- Stop immediately when a part fails.
- Return the completed outcomes in order.
- Do not add parallelism, persistence, retries, or multiple thread strategies.

**Important invariant:**

```text
generate_module reads prompt file -> GenerationRequest.instruction
GuidePromptBuilder consumes request.instruction
GuidePromptBuilder does not reread request.part.prompt_path
```

**Acceptance criteria:**

- One module run uses exactly one thread chain.
- Prompt files execute in deterministic filename order.
- Non-Markdown files and subdirectories are ignored.
- A later failure leaves earlier draft results intact and stops later calls.
- Every prompt file is read exactly once by the workflow path.

---

### Task 6: Test the Module Chain

**File:** `tests/test_workflow.py`

**Focus:** Thread continuity, ordering, discovery, and stopping behavior.

**Instructions:**

- Test that unordered files execute in sorted filename order.
- Test that non-`.md` files and nested directories are ignored.
- Test that the second and later requests receive the thread ID returned by the preceding part.
- Test missing and empty module directories.
- Test empty prompt files.
- Test that a failure on part two prevents part three from running.
- Verify completed outcomes before a failure remain available through written artifacts or the chosen explicit failure contract.

**Acceptance criteria:**

- All tests remain offline.
- The tests would fail if the workflow accidentally started a new thread for each part.
- The tests would fail if prompt order became filesystem-dependent.

---

### Task 7: Implement `GuidePromptBuilder`

**File:** `src/java_quickstart_generator/adapters.py`

**Focus:** Build first-turn and continuation prompts.

**Instructions:**

- Implement the `BuildsPrompt` role.
- On the first turn:
  - read and validate the main guide specification;
  - include the full specification;
  - include the current part instruction; and
  - clearly mark the requested output boundaries.
- On continuation turns:
  - do not repeat the entire guide specification;
  - include a short, stable continuation capsule containing the essential constraints;
  - include the current part instruction; and
  - remind the agent to maintain continuity with earlier parts in the same thread.
- Consume `request.instruction`; do not reread the part prompt path.
- Keep prompt wording stable and testable.

**Acceptance criteria:**

- The full guide specification appears only in a first-turn prompt.
- Later prompts contain the continuation capsule.
- Current instructions appear exactly once.
- Missing or empty guide specifications produce clear errors.
- No Codex SDK call occurs in this adapter.

---

### Task 8: Test `GuidePromptBuilder`

**File:** `tests/test_adapters.py`

**Focus:** Prompt contents and the no-double-read rule.

**Instructions:**

- Test first-turn prompt structure.
- Test continuation prompt structure.
- Test missing and empty guide specifications.
- Test that the current instruction appears once.
- Prove that the builder uses `request.instruction` instead of reopening `part.prompt_path`, for example by using a nonexistent part path with a valid in-memory instruction.

**Acceptance criteria:**

- Tests compare meaningful sections rather than fragile whitespace everywhere.
- Tests prevent accidental full-spec repetition on later turns.
- Tests prevent reintroduction of the double-read bug.

---

### Task 9: Implement `MarkdownWriter`

**File:** `src/java_quickstart_generator/adapters.py`

**Focus:** Safe, deterministic draft writing.

**Instructions:**

- Implement the `WritesArtifact` role.
- Derive a deterministic output path inside the configured drafts directory.
- Preserve module and part ordering in filenames or directories.
- Create required parent directories.
- Write UTF-8 Markdown.
- Reject empty content.
- Prevent output paths from escaping the configured drafts root.
- Do not silently overwrite an existing draft.
- Keep generated drafts trackable by Git.

**Acceptance criteria:**

- Successful writes return the exact created `Path`.
- A path-traversal attempt cannot escape the drafts directory.
- Existing files are not silently replaced.
- Empty output is not written.
- Partial or temporary files are not left behind after an expected failure.

---

### Task 10: Test `MarkdownWriter`

**File:** `tests/test_adapters.py`

**Focus:** Filesystem safety and deterministic output.

**Instructions:**

- Use pytest temporary directories.
- Test successful UTF-8 writing.
- Test parent-directory creation.
- Test empty-content rejection.
- Test collision behavior.
- Test suspicious module IDs, titles, or filenames that might attempt path traversal.
- Test that returned paths remain under the drafts root.

**Acceptance criteria:**

- Tests never touch the real project drafts directory.
- The tests would catch both accidental overwrite and directory escape.

---

### Task 11: Implement `CodexAgent`

**File:** `src/java_quickstart_generator/adapters.py`

**Focus:** Isolate the synchronous Codex SDK integration.

**Instructions:**

- Implement the `RunsAgent` role using the APIs confirmed in Task 0.
- For a request without a thread ID:
  - start a new thread;
  - use the configured model; and
  - use `Sandbox.read_only`.
- For a request with a thread ID:
  - resume that exact thread.
- Run one prompt and return `AgentResponse` with final response text and the actual thread ID.
- Ensure the SDK client is closed even when execution fails.
- Reject an empty final response or missing thread ID.
- Do not log full prompts, credentials, or sensitive environment values.
- Keep the adapter synchronous.

**Acceptance criteria:**

- Start and resume are selected solely from the incoming thread ID.
- The configured default model is not silently replaced by a hard-coded unrelated model.
- The new-thread sandbox is read only.
- The returned thread ID is taken from the SDK thread.
- SDK resources close on both success and failure.

---

### Task 12: Add Offline Tests for `CodexAgent`

**File:** `tests/test_adapters.py`

**Focus:** SDK interaction without a live request.

**Instructions:**

- Use a small fake SDK boundary or monkeypatch the SDK object used by the adapter.
- Test new-thread behavior.
- Test resume behavior.
- Test configured model and read-only sandbox selection.
- Test final response and thread ID mapping.
- Test empty response and missing thread ID failures.
- Test resource closure when `run()` raises.
- Do not make a live API or Codex call.

**Acceptance criteria:**

- Tests are deterministic and credential-free.
- The tests fail if a resume request starts a different thread.
- The tests prove cleanup occurs on exceptions.

---

### Task 13: Update Package Exports

**File:** `src/java_quickstart_generator/__init__.py`

**Focus:** Small, intentional public API.

**Instructions:**

- Export only the models, protocols, adapters, and workflow functions intended for users of the package.
- Remove stale exports.
- Avoid wildcard exports and side effects.

**Acceptance criteria:**

- Every exported name imports successfully.
- Importing the package does not create files or initialize Codex.
- The public surface remains small.

---

### Task 14: Implement CLI Argument Parsing

**File:** `src/java_quickstart_generator/__main__.py`

**Focus:** Parse and validate command-line input without running generation.

**Instructions:**

- Use the standard library unless an existing dependency already provides a justified simpler option.
- Define arguments for:
  - guide specification path;
  - prompts root or module directory;
  - module identifier;
  - drafts directory; and
  - model, with a documented default.
- Keep parsing separate from execution so it can be tested.
- Provide useful `--help` text.

**Acceptance criteria:**

- Valid arguments produce a typed configuration or equivalent input object.
- Missing required values produce normal CLI usage errors.
- Parsing performs no SDK calls and creates no files.

---

### Task 15: Implement CLI Execution

**File:** `src/java_quickstart_generator/__main__.py`

**Focus:** Assemble concrete adapters and call the workflow.

**Instructions:**

- Build the configuration from parsed arguments.
- Construct `GuidePromptBuilder`, `CodexAgent`, and `MarkdownWriter`.
- Invoke `generate_module()` once.
- Print a concise success summary listing created artifacts and the thread ID.
- Convert expected user/configuration failures into concise messages and a nonzero exit code.
- Let unexpected programming failures remain visible enough to diagnose; do not convert every exception into a vague message.
- Do not put workflow logic in the CLI.

**Acceptance criteria:**

- The CLI is composition and presentation only.
- Expected failures return nonzero status.
- Success reports the created artifact paths.
- No secret or full prompt text is printed.

---

### Task 16: Add CLI Tests

**Suggested file:** `tests/test_cli.py`

**Focus:** Argument parsing, composition boundaries, and exit behavior.

**Instructions:**

- Test `--help`.
- Test missing required arguments.
- Test successful execution by replacing the generation boundary with a fake.
- Test expected failure exit codes and messages.
- Test that secrets and full prompt contents are not printed.
- Do not invoke the live Codex SDK.

**Acceptance criteria:**

- CLI tests are offline.
- Both success and expected-failure status codes are asserted.
- Tests do not duplicate workflow tests.

---

### Task 17: Add the Console Entry Point

**File:** `pyproject.toml`

**Focus:** Package invocation through `uv`.

**Instructions:**

- Add one console script entry for `java-quickstart-generator`.
- Point it to the tested CLI entry function.
- Regenerate the lockfile only if required by the metadata change.

**Acceptance criteria:**

- `uv run java-quickstart-generator --help` succeeds.
- `uv run python -m java_quickstart_generator --help` also succeeds if module execution is part of the intended interface.
- No dependency is added merely to create the entry point.

---

### Task 18: Add Prompt and Draft Directory Structure

**Focus:** Make the chaining contract visible in the repository.

**Instructions:**

- Add a minimal `prompts/modules/SEC-XX/` example or documented placeholder structure.
- Establish a tracked `drafts/` directory for generated part drafts.
- Keep `output/` ignored or reserved for assembled/exported artifacts.
- Do not create the complete Java Quickstart content yet.
- Do not add a database or state file.

**Example:**

```text
prompts/
  modules/
    SEC-01/
      01-orientation.md
      02-concepts.md
      03-practice.md
drafts/
output/
```

**Acceptance criteria:**

- Filename ordering maps directly to execution ordering.
- Generated drafts are visible to Git unless deliberately excluded by a later decision.
- Exported/assembled output remains separate from working drafts.

---

### Task 19: Update the README

**File:** `README.md`

**Focus:** Document only implemented behavior.

**Instructions:**

- Explain the purpose and architecture in plain language.
- Show the prompt-directory and draft-directory contract.
- Document setup and commands using `uv` only.
- Explain that one module run uses one Codex thread across ordered prompt files.
- Document current limitations and non-goals.
- Do not claim live behavior that has not been tested.

**Acceptance criteria:**

- A new contributor can install, run help, run tests, and understand where prompts and drafts belong.
- Commands match the actual project configuration.
- Limitations are explicit.

---

### Task 20: Run the Complete Offline Acceptance Suite

**Mode:** Verification; edit only if a narrowly diagnosed defect must be fixed in a separate follow-up task.

Run:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m compileall -q src tests
uv run java-quickstart-generator --help
git diff --check
```

Also inspect `git status --short` and confirm no runtime secrets, caches, or accidental generated files are staged.

**Acceptance criteria:**

- Every command succeeds.
- The test suite makes no network calls.
- The working-tree changes are limited to intended project files.

---

### Task 21: Perform a Read-Only Adversarial Review

**Mode:** Read only

**Focus:** Try to falsify the implementation rather than confirm it.

Use the adversarial-review instructions in the next section. Do not fix findings during this task.

**Deliverable:** A severity-ranked findings report with evidence, reproduction steps, and the smallest reasonable correction for each confirmed issue.

---

### Task 22: Triage the Findings

**Mode:** Planning only

**Focus:** Decide what should be fixed without expanding the PoC.

**Instructions:**

- Classify each finding as:
  - confirmed defect;
  - acceptable PoC limitation;
  - false positive; or
  - deferred enhancement.
- Prioritize correctness, data safety, thread continuity, and test reliability.
- Reject fixes that introduce disproportionate architecture.
- Propose one narrowly scoped task per accepted finding.

**Acceptance criteria:**

- Every review finding has a disposition and rationale.
- Deferred items are not disguised as completed work.
- The fix list remains within the agreed PoC scope.

**Approved dispositions:**

1. Prompt-directory traversal and symlink escape is a confirmed defect. Fix it.
2. Thread continuity is a confirmed defect. Correct the requirement to one Codex
   thread for the entire course, not one thread per module. Context compaction
   inside that thread is acceptable.
3. Failed Codex turns escaping as unclassified `RuntimeError` values is a
   confirmed defect. Translate only SDK turn failures into an expected
   application error.
4. README commands that reference a nonexistent example module are a confirmed
   defect. Correct them.
5. Verbatim CLI exception messages are an acceptable limitation for this local
   PoC. Leave terminal output behavior unchanged, but add a concise code comment
   at the output boundary recording the potential for future SDK exception text
   to contain sensitive details.

---

### Task 23: Apply Accepted Findings One at a Time

**Focus:** Preserve focus and make regressions easy to locate.

For each accepted finding:

1. state the single defect being fixed;
2. add or update a test that reproduces it;
3. implement the smallest correction;
4. run the relevant focused tests;
5. run the complete offline suite; and
6. stop before starting the next finding.

Apply the findings as the following narrowly scoped subtasks.

#### Task 23A: Constrain Prompt Discovery

**Single defect:** A module ID or symlinked prompt can select content outside the
configured prompts directory.

**Tests first:**

- Reject parent-directory traversal in a module ID.
- Reject absolute module IDs.
- Reject a module-directory symlink that resolves outside the prompts root.
- Reject a Markdown-file symlink that resolves outside its module directory.
- Preserve deterministic ordering for ordinary Markdown prompt files.

**Smallest correction:** Resolve the prompt root, module directory, and discovered
prompt paths; require each path to remain under its intended root. Do not add
recursive discovery or a generalized filesystem-security abstraction.

**Acceptance criteria:**

- No prompt outside `prompts/modules/<MODULE_ID>/` can be read.
- Existing prompt filtering and filename ordering remain intact.
- Focused tests and the complete offline suite pass.

#### Task 23B: Enforce One Codex Thread for the Entire Course

**Single defect:** The workflow accepts thread-ID drift and currently scopes thread
continuity to a module rather than to the complete course-generation run.

For this PoC, a **course-generation run** is one invocation that receives one or
more ordered module IDs. It does not require saving thread state between separate
CLI invocations. The Codex SDK may compact context internally; compaction is
acceptable as long as the Codex thread identity remains unchanged.

**Tests first:**

- Generate at least two modules with at least two total parts.
- Verify the first course part starts a thread and every later part, including
  the first part of a later module, resumes the same exact thread ID.
- Make a continuation return a different thread ID and verify generation stops.
- Verify no later part or module runs after thread-ID drift.
- Preserve single-module invocation as a valid one-module course run.

**Smallest correction:**

- Add a narrow course-level workflow that accepts ordered module IDs and carries
  one canonical thread ID across module boundaries.
- Allow the CLI to accept one or more module IDs in a single invocation.
- Let the first generated part establish the canonical thread ID.
- Require every subsequent response to return that exact ID.
- Keep module and part ordering deterministic.
- Do not add persisted thread state, retries, recovery orchestration, or multiple
  thread strategies.

**Acceptance criteria:**

- All generated content in one course-generation run comes from one Codex thread.
- Context compaction does not count as a thread change.
- Thread-ID drift fails clearly and stops the remaining course chain.
- Earlier successful drafts remain available after a later failure.
- Focused tests and the complete offline suite pass.

#### Task 23C: Classify Failed Codex Turns

**Single defect:** The installed SDK can raise `RuntimeError` for a failed turn,
while the CLI treats every `RuntimeError` as an unexpected programming error.

**Tests first:**

- Simulate `thread.run()` raising `RuntimeError` for a failed SDK turn.
- Verify the SDK adapter translates it into one narrow application exception.
- Verify the CLI returns a nonzero status for that exception.
- Verify unrelated `RuntimeError` values outside the SDK call still propagate.

**Smallest correction:** Catch `RuntimeError` only around the SDK `thread.run()`
boundary, chain it into a small application-specific generation exception, and
handle that exception as an expected CLI failure. Do not create a broad exception
hierarchy or catch all runtime errors globally.

**Acceptance criteria:**

- A failed Codex turn produces a controlled nonzero CLI result.
- Unexpected programming errors remain diagnosable.
- Focused tests and the complete offline suite pass.

#### Task 23D: Correct and Extend the README

**Single defect:** The documented command references a nonexistent module and the
thread description states the obsolete per-module boundary.

**Smallest correction:**

- Use the included `SEC-XX` module in runnable examples.
- Document that one or more module IDs supplied in one invocation form a
  course-generation run.
- State that the entire course-generation run uses one Codex thread, even if the
  SDK compacts its context.
- Clearly identify which command invokes the configured Codex service.

**Acceptance criteria:**

- Every runnable example references paths and modules present in the repository.
- The README accurately describes course-wide thread continuity and CLI syntax.
- Offline setup commands remain clearly separated from live generation.

#### Task 23E: Record the Accepted CLI Exception-Output Risk

**Disposition:** Accept the current terminal exception output for this local PoC.
Do not sanitize or suppress it in this task.

**Smallest correction:** Add a concise comment beside the CLI exception-output
boundary explaining that SDK exception text could contain sensitive details in a
future or less-trusted deployment and should be sanitized before broader use.

**Acceptance criteria:**

- Runtime behavior and exit statuses are unchanged.
- The comment describes the concrete risk without claiming a current leak.
- No logging framework, debug mode, or exception-redaction subsystem is added.

**Acceptance criteria:**

- Every correction has a regression test when practical.
- Unrelated refactoring is excluded.
- The full offline suite remains green after each fix.

---

### Task 24: Repeat the Adversarial Review

**Mode:** Read only

**Focus:** Verify that corrections worked and did not create new failure modes.

**Acceptance criteria:**

- Earlier confirmed defects can no longer be reproduced.
- Any new findings are reported separately.
- The reviewer does not silently edit the implementation.

## Adversarial Review Instructions

Use the following as the review prompt:

```text
Act as an adversarial reviewer of this small Python proof of concept.
Your job is to falsify its correctness, safety, and stated architecture.
Do not edit any files.

Read the implementation, inline comments, tests, pyproject.toml, README,
.gitignore, and lockfile. Run only read-only inspections and the existing
offline quality/test commands.

Look specifically for evidence that:

1. a continuation accidentally starts or resumes the wrong Codex thread;
2. module parts can run out of filename order;
3. non-prompt files or directories can be executed;
4. the full guide specification is repeated on every turn, or later turns lose
   the essential constraints;
5. a part prompt is read twice through separate workflow and builder paths;
6. generated content can overwrite an existing draft, escape the drafts root,
   or create an empty artifact;
7. execution continues after a failed part;
8. expected CLI failures return a success exit code;
9. tests make live Codex or network calls;
10. the model or sandbox is hard-coded incorrectly;
11. prompts, credentials, environment values, or other sensitive data can leak
    through output or logs;
12. the Codex SDK client is not closed on success or failure;
13. README claims exceed implemented and tested behavior;
14. unnecessary frameworks, persistence, retry systems, plugin systems,
    asynchronous code, or other scope creep were introduced;
15. type checking passes only because important values are typed as Any;
16. tests assert implementation details while missing observable failures.

For every confirmed issue, report:

- severity: critical, high, medium, or low;
- exact file and line;
- violated acceptance criterion;
- a minimal reproduction or reasoning trace;
- likely user impact; and
- the smallest reasonable correction.

Separate confirmed findings from questions, acceptable PoC limitations, and
optional enhancements. Do not report style preferences as defects. If no
confirmed defect exists in an area, say what evidence you checked.
```

## Project-Level Acceptance Criteria

### Architecture

- Data classes are passive and typed.
- Protocols are narrow and express behavior rather than inheritance hierarchy.
- Workflow functions depend on protocols, not concrete adapters.
- Adapters isolate prompt formatting, SDK access, and filesystem writing.
- The CLI handles argument parsing, dependency assembly, presentation, and exit status only.
- No dependency-injection framework, database, plugin framework, or elaborate class hierarchy is introduced.

### Prompt Chaining

- One course-generation run uses one Codex thread across every requested module.
- The first course part starts the thread; all later parts, including parts in
  later modules, resume that same thread.
- Codex SDK context compaction is acceptable and does not change the thread
  continuity requirement.
- Prompt files run in deterministic filename order.
- The full guide specification is included only on the first turn.
- Later turns receive a stable continuation capsule plus their current instruction.
- Each part prompt is read only once along the generation path.

### Filesystem Behavior

- Only regular `.md` prompt files are discovered.
- All generated draft paths remain under the configured drafts directory.
- Existing drafts are not silently overwritten.
- Empty content is not written.
- Text uses UTF-8.
- Earlier successful drafts remain available if a later part fails.
- Working drafts are visible to Git; assembled/exported output is kept separate.

### Failure Behavior

- Missing guide specifications fail clearly.
- Missing or empty module directories fail clearly.
- Empty prompt files fail clearly.
- Empty agent responses fail clearly.
- A missing thread ID fails clearly.
- The chain stops on the first failure.
- Expected CLI failures return a nonzero exit status.
- Unexpected programming errors remain diagnosable.

### Codex SDK Boundary

- The project uses the stable `openai-codex` dependency already managed by `uv`.
- Execution remains synchronous for this PoC.
- New threads use the configured default model and `Sandbox.read_only`.
- Existing threads are resumed with the supplied ID.
- SDK resources close on both success and failure.
- Unit and acceptance tests do not make live calls.
- Prompts, credentials, and sensitive environment values are not logged.

### Quality Gate

All of the following pass:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m compileall -q src tests
uv run java-quickstart-generator --help
git diff --check
```

## Explicit Non-Goals

Do not add these during the proof of concept:

- database-backed state;
- retry or recovery orchestration;
- parallel or asynchronous generation;
- multiple simultaneous thread strategies;
- a plugin system;
- a web interface;
- automatic Git commits;
- automatic guide assembly or publication;
- generative video production;
- a generalized course-authoring platform.

These may become later projects after the basic chain is proven.

## Optional Live Smoke Test

This test requires explicit authorization because it invokes the live Codex service.

Use a temporary test module with two very short prompt files:

1. Part one defines a small fact or structure.
2. Part two must explicitly use that fact or structure.

Verify:

- exactly two turns run;
- both turns use the same thread ID;
- two draft files are created;
- the second draft demonstrates awareness of the first turn;
- no unrelated project file changes;
- prompts and credentials are not printed.

Do not commit smoke-test drafts. Do not delete material user files as cleanup. If cleanup would remove anything outside clearly temporary test artifacts, ask first.

## How to Use This Plan in a Chained Session

For each task:

1. Copy the global prompting rules.
2. Add the text for exactly one numbered task.
3. Ask the agent to inspect the current working tree before editing.
4. Review its reported changes and verification results.
5. Resolve failures before moving forward.
6. Begin the next task in the same conversation so the context is preserved.

Do not combine tasks merely to reduce the number of prompts. The small steps are intentional: they make architectural drift, SDK mistakes, and thread-continuity defects easier to detect.
