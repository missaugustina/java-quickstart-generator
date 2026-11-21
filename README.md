# Quickstart Generator

A small Python proof of concept for generating modular quickstart content with the OpenAI Codex
SDK. It runs one or more ordered sections in a single Codex thread and saves each response as a
separate Markdown draft for human review.

The generator is intentionally narrow. It demonstrates prompt chaining, replaceable behavioral
roles, and safe draft writing without becoming a generalized course-authoring platform.

## How it works

The generator safely parses a YAML course specification and validates its sections and shared
section template. It generates one Markdown draft per section, with one Codex turn per section.
All turns in a run use the same Codex thread ID; context compaction is acceptable. Separate CLI
invocations start separate threads.

Before calling Codex, it checks requested IDs and all planned drafts for collisions. It stops on
the first generation failure and retains completed drafts. Existing drafts are never overwritten.

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
uv run quickstart-generator --help
```

The equivalent module command is:

```shell
uv run python -m quickstart_generator --help
```

Run these commands from the repository root. The following generation commands invoke the
configured Codex service. They may require
authentication and may consume service resources.

The bundled example is **Create a clear GitHub issue in 20 minutes**. It introduces GitHub
issues through a fictional README setup instruction that does not name the folder in which
to run a command. The learner outlines the problem, writes an issue draft, and checks that
another person could act on it. A saved draft completes the exercise; posting is optional
and limited to a practice repository. No Git, branch, or pull request knowledge is required.

| Section | Learner time | Result |
|---|---|---|
| `SEC-01` | 8 minutes | Four notes outlining the README problem |
| `SEC-02` | 12 minutes | A clear issue title and description, checked for missing details |

The 20 minutes describe the learner's exercise, not the generator's runtime. Generate both
sections in YAML order, with each Markdown draft saved under `drafts/<SECTION_ID>/01-section.md`:

```shell
uv run quickstart-generator
```

Generate only the first section:

```shell
uv run quickstart-generator SEC-01
```

To create a course on another topic, copy the example to a new file:

```shell
cp -n prompts/example_course.yaml prompts/my_course.yaml
```

Edit `course_context` to define your topic, audience, prerequisites, goal, assignment, and
time budget. Update each section's purpose, topics, assignment connection, activity, and layout
to support that assignment. Keep IDs unique and put sections in learning order. The complete
YAML, including `course_context`, reaches the initial generation turn. Then select your copy:

```shell
uv run quickstart-generator --course-spec prompts/my_course.yaml
```

Optional arguments:

| Argument | Default | Meaning |
|---|---|---|
| `SEC_ID ...` | All sections | Select sections in requested order |
| `--course-spec PATH` | `prompts/example_course.yaml` | YAML course source |
| `--prompt-template PATH` | Bundled Markdown template | Custom prompt wording and arrangement |
| `--drafts-directory PATH` | `drafts` | Destination for drafts |
| `--model MODEL` | Configured Codex default | Model override |

The YAML must contain a nonempty `guide_structure.sections` list. Each section requires a unique
safe `id`, `title`, `map_location`, `purpose`, `topics`, `assignment_connection`, `activity`, and
`layout`. Topics and layout are nonempty lists of text. The shared
`section_template.required_blocks` list requires a positive unique `order`, `name`, and
`instruction` for each block.

The first turn receives the complete specification. Later turns receive the current section,
shared section blocks, and continuity rules in the same Codex thread. Each draft is written to
`drafts/<SECTION_ID>/01-section.md`. Move an existing draft before generating that section again.

The tracked `prompts/example_course.yaml` contains the GitHub demonstration course and is
available in a fresh clone. Custom course copies are visible to Git unless you ignore them.
On this machine,
`prompts/guide_spec.yaml` is an ignored personal specification; it is absent from a fresh clone.
Select a personal file explicitly with `--course-spec`. Drafts remain visible to Git; review
their contents before committing. `output/` remains reserved for future exports.

## Customize the prompt

The YAML specification describes the course. A Markdown template controls the generation
instructions and how section data appears in each prompt. Edit a copy of the template to
change those instructions without editing Python.

The default is bundled at
`src/quickstart_generator/templates/course_prompt.md`. It also ships inside the installed
package and loads independently of the working directory. Custom template and course-spec paths
are resolved from your working directory. The template is loaded and validated once per run;
edits made during a run apply to the next run.

From the repository root, copy the default:

```shell
cp -n src/quickstart_generator/templates/course_prompt.md prompts/my_course_prompt.md
```

Edit the copy. For example, add “Use short paragraphs and concrete examples” beneath the
initial and continuation headings. Then select it:

```shell
uv run quickstart-generator SEC-01 \
  --course-spec prompts/example_course.yaml \
  --prompt-template prompts/my_course_prompt.md
```

On this machine, `prompts/guide_prompt_original.md` preserves earlier course-specific guidance.
Select that path with `--prompt-template` to use it. It is ignored by Git and absent from a fresh
clone. Other custom templates are visible to Git unless you ignore them yourself.

### Reserved headings

Keep these three exact top-level headings, each once, in this order. Start the file with the
first heading; leading blank lines are allowed. Use lower-level headings inside the blocks.

| Heading | Used when | Content |
|---|---|---|
| `# Initial turn` | First section in a run | Initial instructions and complete course context |
| `# Continuation turn` | Every later section | Continuity instructions |
| `# Current section` | Every turn | Current section data and output requirements |

The renderer chooses one turn block and appends the current-section block once. The complete
YAML context naturally also contains the selected section's source data.

### Placeholder contract

Use `$name` or `${name}`. The initial block must contain `$course_spec` exactly once. The
continuation block must contain no placeholders. The current-section block must contain each
remaining placeholder below exactly once. Keep placeholders in their assigned blocks.

| Placeholder | Supplied value |
|---|---|
| `$course_spec` | Complete course YAML, with outer whitespace trimmed |
| `$section_id` | Current section ID |
| `$section_title` | Section title |
| `$source_filename` | YAML filename without its directory |
| `$map_location` | Section location in the course map |
| `$purpose` | Section purpose |
| `$topics` | Topic list formatted as Markdown bullets |
| `$assignment_connection` | Connection to the assignment |
| `$activity` | Practice activity |
| `$layout` | Layout requirements formatted as Markdown bullets |
| `$required_blocks` | Shared section blocks sorted by their order values |

Write `$$` for a literal dollar sign in template prose: `$$5` renders as `$5`. Inserted YAML
values are substituted once and remain literal, so dollar signs and placeholder-looking text
inside course data do not need escaping. Templates support substitution only, with no loops,
conditions, expressions, or code execution.

All three blocks are validated before the CLI creates a Codex agent, even when only one section
is selected. Missing files, invalid UTF-8, empty blocks, missing or repeated headings, malformed
placeholders, and unknown, missing, repeated, or misplaced placeholders stop the run with an
error. The command does not fall back to the default when a custom template is invalid.

## Architecture

The design uses small structural roles rather than a deep class hierarchy:

| Layer | Responsibility |
|---|---|
| `course_spec.py` | YAML parsing and structural validation |
| `models.py` | Immutable data passed through the application |
| `roles.py` | Narrow `Protocol` contracts for prompt building, agent execution, and writing |
| `prompt_template.py` | Markdown template loading, validation, and literal substitution |
| `templates/course_prompt.md` | Editable default generation guidance |
| `adapters.py` | Template-backed prompt builder, Codex SDK access, and safe Markdown writing |
| `workflow.py` | YAML section selection, draft preflight, and sequential course generation |
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
uv run quickstart-generator --help
uv build
git diff --check
```

## Current validation status

The workflow, adapters, filesystem protections, and CLI are covered by offline automated tests.
The Codex adapter tests use a fake SDK boundary and do not require credentials or network access.
Template tests cover customization through the CLI, literal substitution, and validation before
agent creation. A packaging test builds and installs a wheel in a temporary directory, then
loads and renders the bundled template outside the repository. Its build and installation use
`--offline`; run `uv sync --locked` first to populate the required build dependencies.

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
- finished course content; or
- generative video production.

## Documentation

- [Project repository](https://github.com/missaugustina/quickstart-generator)
- [OpenAI Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [`uv` documentation](https://docs.astral.sh/uv/)

## Course section IDs

Section IDs must be unique even when letter case differs (for example, `SEC-01` and
`sec-01`). Each ID becomes a draft directory name, and some filesystems treat
those names as the same directory. The YAML loader also rejects repeated keys
and YAML merge keys (`<<`) so course instructions are unambiguous.
