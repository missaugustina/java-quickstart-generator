"""Offline tests for command-line parsing, composition, and reporting."""

from pathlib import Path
from typing import cast

import pytest

import java_quickstart_generator.__main__ as cli
from java_quickstart_generator.adapters import (
    CodexAgent,
    GenerationError,
    GuidePromptBuilder,
    MarkdownWriter,
)
from java_quickstart_generator.models import (
    AgentResponse,
    GenerationOutcome,
    GeneratorConfig,
    ModulePart,
)


def test_help_exits_successfully_without_running_generation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_generation(**kwargs: object) -> list[GenerationOutcome]:
        raise AssertionError(f"Generation must not run for --help: {kwargs}")

    monkeypatch.setattr(cli, "generate_yaml_course", unexpected_generation)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert "usage: java-quickstart-generator" in captured.out
    assert "SEC_ID" in captured.out
    assert "--course-spec" in captured.out
    assert "--prompts-directory" not in captured.out
    assert "--drafts-directory" in captured.out
    assert "--model" in captured.out
    assert captured.err == ""


def test_no_section_ids_selects_all() -> None:
    arguments = cli.parse_args([])
    assert arguments.module_ids == ()
    assert arguments.config.guide_spec == Path("prompts/example_course.yaml")


def test_success_composes_adapters_and_reports_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module_ids = ("SEC-01", "SEC-02")
    part_one = ModulePart(module_ids[0], Path("01-map.md"), "Map")
    part_two = ModulePart(module_ids[1], Path("01-concepts.md"), "Concepts")
    outcomes = [
        GenerationOutcome(part_one, Path("drafts/SEC-01/01-map.md"), "course-thread"),
        GenerationOutcome(part_two, Path("drafts/SEC-02/01-concepts.md"), "course-thread"),
    ]
    received: dict[str, object] = {}

    def fake_generate_course(**kwargs: object) -> list[GenerationOutcome]:
        received.update(kwargs)
        return outcomes

    monkeypatch.setattr(cli, "generate_yaml_course", fake_generate_course)
    secret_model = "MODEL_VALUE_MUST_NOT_BE_PRINTED"

    status = cli.main(
        [
            *module_ids,
            "--course-spec",
            "custom/guide.yaml",
            "--drafts-directory",
            "custom/drafts",
            "--model",
            secret_model,
        ]
    )

    captured = capsys.readouterr()
    config = received["config"]
    prompt_builder = received["prompt_builder"]
    agent = received["agent"]
    writer = received["writer"]
    assert status == 0
    assert received["section_ids"] == module_ids
    assert isinstance(config, GeneratorConfig)
    assert config.guide_spec == Path("custom/guide.yaml")
    assert config.drafts_directory == Path("custom/drafts")
    assert isinstance(prompt_builder, GuidePromptBuilder)
    assert isinstance(agent, CodexAgent)
    assert agent.model == secret_model
    assert isinstance(writer, MarkdownWriter)
    assert "Generated 2 draft(s) for course modules SEC-01, SEC-02" in captured.out
    assert "drafts/SEC-01/01-map.md" in captured.out
    assert "drafts/SEC-02/01-concepts.md" in captured.out
    assert "Codex thread: course-thread" in captured.out
    assert secret_model not in captured.out
    assert captured.err == ""


def test_expected_generation_failure_returns_nonzero_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_generation(**kwargs: object) -> list[GenerationOutcome]:
        module_ids = ", ".join(cast(tuple[str, ...], kwargs["section_ids"]))
        raise FileNotFoundError(f"missing module prompts for {module_ids}")

    monkeypatch.setattr(cli, "generate_yaml_course", fail_generation)

    status = cli.main(["SEC-404"])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert "Could not generate course modules SEC-404" in captured.err
    assert "missing module prompts for SEC-404" in captured.err


def test_failed_codex_turn_returns_nonzero_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_generation(**kwargs: object) -> list[GenerationOutcome]:
        raise GenerationError("Codex turn failed: service unavailable")

    monkeypatch.setattr(cli, "generate_yaml_course", fail_generation)

    status = cli.main(["SEC-01"])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert "Could not generate course modules SEC-01" in captured.err
    assert "Codex turn failed: service unavailable" in captured.err


def test_full_prompt_and_sensitive_values_are_not_printed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    guide_secret = "FULL_GUIDE_SECRET_MUST_NOT_BE_PRINTED"
    instruction_secret = "PART_INSTRUCTION_SECRET_MUST_NOT_BE_PRINTED"
    model_secret = "MODEL_SECRET_MUST_NOT_BE_PRINTED"
    guide_spec = tmp_path / "course.yaml"
    guide_spec.write_text(
        f"""context: {guide_secret}
guide_structure:
  sections:
    - id: SEC-01
      title: Example
      map_location: MAP-1
      purpose: {instruction_secret}
      topics: [Types]
      assignment_connection: Apply it
      activity: Trace it
      layout: [Example]
section_template:
  required_blocks:
    - order: 1
      name: Location
      instruction: Find it
""",
        encoding="utf-8",
    )
    drafts_directory = tmp_path / "drafts"

    class CapturingAgent:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
            self.prompts.append(prompt)
            return AgentResponse("generated draft", "thread-1")

    capturing_agent = CapturingAgent()

    def fake_agent_factory(model: str | None) -> CapturingAgent:
        assert model == model_secret
        return capturing_agent

    monkeypatch.setattr(cli, "CodexAgent", fake_agent_factory)

    status = cli.main(
        [
            "SEC-01",
            "--course-spec",
            str(guide_spec),
            "--drafts-directory",
            str(drafts_directory),
            "--model",
            model_secret,
        ]
    )

    captured = capsys.readouterr()
    assert status == 0
    assert len(capturing_agent.prompts) == 1
    assert guide_secret in capturing_agent.prompts[0]
    assert instruction_secret in capturing_agent.prompts[0]
    combined_output = captured.out + captured.err
    assert guide_secret not in combined_output
    assert instruction_secret not in combined_output
    assert model_secret not in combined_output
    assert (drafts_directory / "SEC-01" / "01-section.md").read_text(
        encoding="utf-8"
    ) == "generated draft"


def test_unexpected_programming_error_remains_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_unexpectedly(**kwargs: object) -> list[GenerationOutcome]:
        module_ids = ", ".join(cast(tuple[str, ...], kwargs["section_ids"]))
        raise RuntimeError(f"programming failure for {module_ids}")

    monkeypatch.setattr(cli, "generate_yaml_course", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="programming failure for SEC-01"):
        cli.main(["SEC-01"])
