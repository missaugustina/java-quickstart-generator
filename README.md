# Java Quickstart Generator

Python project scaffold for generating a modular Java quickstart guide with the
OpenAI Codex SDK.

The application entry point has intentionally not been created yet. The package
contains only typed models, small role contracts, a minimal workflow, and
adapter stubs.

## Project environment

- Python 3.12, installed and selected by `uv`
- Project-local virtual environment at `.venv`
- OpenAI Codex SDK package: `openai-codex`
- Development tools: Ruff, Pyright, and pytest

## Setup

```shell
uv sync
```

Use the project interpreter located at:

```text
.venv/bin/python
```

## Dependency commands

```shell
uv add <package>
uv add --dev <package>
uv remove <package>
uv lock --upgrade
```

Do not install project dependencies with the system `pip` command. Run Python
and development tools through `uv run` or the project-local interpreter.

## Planned structure

```text
java-quickstart-generator/
|-- prompts/       Prompt specifications and module templates
|-- src/
|   `-- java_quickstart_generator/
|       |-- models.py    Immutable workflow values
|       |-- roles.py     Narrow behavioral protocols
|       |-- workflow.py  Generate one module part
|       `-- adapters.py  Codex, YAML, and Markdown stubs
|-- tests/         Future automated tests
|-- output/        Generated guide content; ignored by Git
|-- pyproject.toml Project metadata and dependency declarations
`-- uv.lock        Reproducible dependency lockfile
```

## Design boundary

The PoC follows a role-oriented style:

- Dataclasses hold state and identity.
- Protocols define small, independent behaviors.
- The workflow coordinates those behaviors through dependency injection.
- Concrete adapters will connect YAML, the Codex SDK, and Markdown output.

The first increment intentionally has no CLI framework, database, plugin
registry, or generalized workflow engine.

## Useful checks

After source code is added:

```shell
uv run ruff check .
uv run pyright
uv run pytest
```

## Documentation

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [uv](https://docs.astral.sh/uv/)
