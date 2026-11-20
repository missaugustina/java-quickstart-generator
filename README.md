# Java Quickstart Generator

A small Python proof of concept for generating a modular Java refresher with the OpenAI Codex
SDK. It runs one or more ordered modules in a single Codex thread and saves each response as a
separate Markdown draft for human review.

The generator is intentionally narrow. It demonstrates prompt chaining, replaceable behavioral
roles, and safe draft writing without becoming a generalized course-authoring platform.

## How it works

```text
guide specification + ordered course modules + ordered part prompts
                              |
                              v
                      GuidePromptBuilder
                              |
                              v
          one Codex thread across every module and part
                              |
                              v
                       MarkdownWriter
                              |
                              v
                    tracked Markdown drafts
```

For one course-generation run, the application:

1. Processes the module IDs in the order supplied on the command line.
2. Finds regular Markdown files in each `prompts/modules/<MODULE_ID>/` directory.
3. Sorts each module's parts by filename, such as `01-orientation.md` before
   `02-concepts.md`.
4. Includes the complete guide specification in the first course prompt only.
5. Starts one Codex thread with a read-only sandbox.
6. Resumes that exact thread for every later part, including parts in later modules.
7. Writes one draft per successful prompt under `drafts/<MODULE_ID>/`.
8. Stops on the first failure while leaving earlier successful drafts available.

Codex may compact its internal context during a long course run. Compaction is acceptable: every
generation call must still use the same Codex thread ID. This PoC does not persist that thread ID
between separate CLI invocations.

The guide specification is read as UTF-8 text and included in the first prompt. Its `.yaml`
extension makes the example easy for a human to structure; this PoC does not parse or validate
the YAML schema.

## Requirements and setup

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)
- A local environment in which the OpenAI Codex SDK can authenticate and run

Install the locked project environment:

```shell
uv sync --locked
```

The project interpreter is:

```text
.venv/bin/python
```

Use this interpreter in PyCharm. Manage packages through `uv`; do not install project
dependencies with the system Python or system `pip`.

## Command-line usage

Show the available arguments without running generation:

```shell
uv run java-quickstart-generator --help
```

The equivalent module command is:

```shell
uv run python -m java_quickstart_generator --help
```

The following generation commands invoke the configured Codex service. They may require
authentication and may consume service resources.

Generate the included `SEC-XX` example as a one-module course run using the default paths and the
user's configured Codex model:

```shell
uv run java-quickstart-generator SEC-XX
```

To generate a multi-module course, supply its existing module directory names in the desired
course order. For example, a course containing `SEC-01` and `SEC-02` would use the positional form
`MODULE_ID [MODULE_ID ...]` with `SEC-01` followed by `SEC-02`.

Override every configurable input:

```shell
uv run java-quickstart-generator SEC-XX \
  --guide-spec prompts/guide_spec.yaml \
  --prompts-directory prompts/modules \
  --drafts-directory drafts \
  --model MODEL_NAME
```

Defaults:

| Input | Default | Meaning |
|---|---|---|
| `MODULE_ID [MODULE_ID ...]` | Required | One or more existing module directories, in course order |
| `--guide-spec` | `prompts/guide_spec.yaml` | Shared guide context |
| `--prompts-directory` | `prompts/modules` | Root containing module directories |
| `--drafts-directory` | `drafts` | Root for reviewable part drafts |
| `--model` | Codex configured default | Optional model override for the course thread |

The command reports generated artifact paths and the shared course thread ID. It does not print
the full guide specification, part prompts, or model value.

## Directory contract

```text
java-quickstart-generator/
|-- prompts/
|   |-- guide_spec.yaml
|   `-- modules/
|       `-- SEC-XX/
|           `-- 01-example.md
|-- drafts/
|   `-- <MODULE_ID>/
|       `-- <ordered-part>.md
|-- output/
|-- src/java_quickstart_generator/
|   |-- __main__.py
|   |-- adapters.py
|   |-- models.py
|   |-- roles.py
|   `-- workflow.py
|-- tests/
|-- pyproject.toml
`-- uv.lock
```

- `prompts/` contains source specifications and ordered generation instructions.
- `drafts/` contains working drafts. These files are visible to Git so they can be reviewed and
  compared. Do not place sensitive generated content here unless it is appropriate to commit.
- `output/` is reserved for later assembled or exported artifacts and is ignored by Git.
- Existing drafts are never silently overwritten. Move or rename an existing draft before
  intentionally generating the same part again.

The included `SEC-XX` module is a structural example, not completed Java course content.

## Architecture

The design uses small structural roles rather than a deep class hierarchy:

| Layer | Responsibility |
|---|---|
| `models.py` | Immutable data passed through the application |
| `roles.py` | Narrow `Protocol` contracts for prompt building, agent execution, and writing |
| `adapters.py` | Guide prompt formatting, Codex SDK access, and safe Markdown writing |
| `workflow.py` | Single-part orchestration plus ordered module and course chaining |
| `__main__.py` | Argument parsing, dependency composition, reporting, and exit status |

The workflow depends on protocols rather than concrete adapters. Tests can therefore use small
offline fakes without contacting Codex.

## Development checks

Run the complete offline verification suite:

```shell
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m compileall -q src tests
uv run java-quickstart-generator --help
git diff --check
```

## Current validation status

The workflow, adapters, filesystem protections, and CLI are covered by offline automated tests.
The Codex adapter tests use a fake SDK boundary and do not require credentials or network access.

A live end-to-end Codex generation has **not** been run as part of the automated suite. Live model
behavior, authentication, runtime availability, cost, and response quality remain to be validated
separately with explicit authorization.

## Current limitations and non-goals

This proof of concept does not provide:

- retry or resume-after-process-termination support;
- thread persistence between separate CLI invocations;
- database-backed generation state;
- parallel or asynchronous generation;
- multiple simultaneous thread strategies;
- automatic draft overwrite or versioning;
- guide assembly, export, or publication;
- automatic Git commits;
- a plugin system, web interface, or generalized workflow engine;
- finished Java Quickstart course content; or
- generative video production.

## Documentation

- [OpenAI Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [`uv` documentation](https://docs.astral.sh/uv/)
