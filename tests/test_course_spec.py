"""Offline validation tests for YAML course specifications."""

from pathlib import Path
from typing import Any

import pytest
import yaml

import java_quickstart_generator.__main__ as cli
from java_quickstart_generator.adapters import GuidePromptBuilder, MarkdownWriter
from java_quickstart_generator.course_spec import load_course_spec
from java_quickstart_generator.models import AgentResponse, GeneratorConfig
from java_quickstart_generator.workflow import generate_yaml_course


def sample_spec() -> dict[str, Any]:
    return {
        "guide_structure": {
            "sections": [
                {
                    "id": "SEC-02",
                    "title": "Second",
                    "map_location": "MAP-2",
                    "purpose": "Learn a concept",
                    "topics": ["Types"],
                    "assignment_connection": "Apply a type",
                    "activity": "Trace a value",
                    "layout": ["Example", "Exercise"],
                },
                {
                    "id": "SEC-01",
                    "title": "First",
                    "map_location": "MAP-1",
                    "purpose": "Learn another concept",
                    "topics": ["Methods"],
                    "assignment_connection": "Apply a method",
                    "activity": "Trace a call",
                    "layout": ["Example"],
                },
            ]
        },
        "section_template": {
            "required_blocks": [
                {"order": 2, "name": "Practice", "instruction": "Try it"},
                {"order": 1, "name": "Location", "instruction": "Find it"},
            ]
        },
    }


def write_spec(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "course.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_load_preserves_section_order_and_sorts_blocks(tmp_path: Path) -> None:
    spec = load_course_spec(write_spec(tmp_path, sample_spec()))
    assert [section.id for section in spec.sections] == ["SEC-02", "SEC-01"]
    assert [block.name for block in spec.required_blocks] == ["Location", "Practice"]
    assert spec.sections[0].topics == ("Types",)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("empty_sections", "nonempty list"),
        ("unsafe_id", "unsafe"),
        ("duplicate_id", "Duplicate"),
        ("missing_purpose", "SEC-02.purpose"),
        ("empty_blocks", "nonempty list"),
    ],
)
def test_rejects_invalid_structure(tmp_path: Path, change: str, message: str) -> None:
    data = sample_spec()
    if change == "empty_sections":
        data["guide_structure"]["sections"] = []
    elif change == "unsafe_id":
        data["guide_structure"]["sections"][0]["id"] = "../bad"
    elif change == "duplicate_id":
        data["guide_structure"]["sections"][1]["id"] = "SEC-02"
    elif change == "missing_purpose":
        del data["guide_structure"]["sections"][0]["purpose"]
    elif change == "empty_blocks":
        data["section_template"]["required_blocks"] = []
    with pytest.raises(ValueError, match=message):
        load_course_spec(write_spec(tmp_path, data))


def test_rejects_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "course.yaml"
    path.write_text("guide_structure: [unterminated", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_course_spec(path)


def test_section_prompts_include_section_data_and_only_initial_full_spec(tmp_path: Path) -> None:
    data = sample_spec()
    data["private_course_context"] = "Full specification marker"
    spec = load_course_spec(write_spec(tmp_path, data))
    section = spec.sections[0]
    builder = GuidePromptBuilder()

    first = builder.build_section_prompt(section, spec, None)
    later = builder.build_section_prompt(section, spec, "course-thread")

    for prompt in (first, later):
        for expected in (
            "SEC-02",
            "Second",
            "MAP-2",
            "Learn a concept",
            "Types",
            "Apply a type",
            "Trace a value",
            "Example",
            "1. Location: Find it",
            "2. Practice: Try it",
        ):
            assert expected in prompt
        assert prompt.index("1. Location") < prompt.index("2. Practice")

    assert "Full specification marker" in first
    assert "Full specification marker" not in later
    assert "## Complete guide specification" not in later


class CourseAgent:
    def __init__(self, responses: list[AgentResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str | None]] = []

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        self.calls.append((prompt, thread_id))
        return self.responses[len(self.calls) - 1]


@pytest.mark.parametrize("requested", [[], ["SEC-01", "SEC-02"]])
def test_yaml_course_uses_one_thread_and_explicit_outputs(
    tmp_path: Path, requested: list[str]
) -> None:
    path = write_spec(tmp_path, sample_spec())
    config = GeneratorConfig(path, tmp_path / "drafts")
    agent = CourseAgent([AgentResponse("first", "thread"), AgentResponse("second", "thread")])
    outcomes = generate_yaml_course(
        requested, config, GuidePromptBuilder(), agent, MarkdownWriter()
    )
    assert [outcome.part.module_id for outcome in outcomes] == (requested or ["SEC-02", "SEC-01"])
    assert [thread for _, thread in agent.calls] == [None, "thread"]
    assert all(outcome.artifact_path.name == "01-section.md" for outcome in outcomes)
    assert "Complete guide specification" in agent.calls[0][0]
    assert "Complete guide specification" not in agent.calls[1][0]


def test_yaml_course_stops_before_writing_changed_thread(tmp_path: Path) -> None:
    path = write_spec(tmp_path, sample_spec())
    config = GeneratorConfig(path, tmp_path / "drafts")
    agent = CourseAgent([AgentResponse("first", "thread"), AgentResponse("second", "changed")])
    with pytest.raises(ValueError, match="different Codex thread"):
        generate_yaml_course([], config, GuidePromptBuilder(), agent, MarkdownWriter())
    assert (config.drafts_directory / "SEC-02" / "01-section.md").read_text() == "first"
    assert not (config.drafts_directory / "SEC-01").exists()


@pytest.mark.parametrize("requested", [["unknown"], ["SEC-01", "SEC-01"]])
def test_yaml_course_rejects_selection_before_codex(tmp_path: Path, requested: list[str]) -> None:
    path = write_spec(tmp_path, sample_spec())
    config = GeneratorConfig(path, tmp_path / "drafts")
    agent = CourseAgent([])
    with pytest.raises(ValueError):
        generate_yaml_course(requested, config, GuidePromptBuilder(), agent, MarkdownWriter())
    assert not agent.calls


def test_yaml_course_preflights_later_draft_collision(tmp_path: Path) -> None:
    path = write_spec(tmp_path, sample_spec())
    config = GeneratorConfig(path, tmp_path / "drafts")
    existing = config.drafts_directory / "SEC-01" / "01-section.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep")
    agent = CourseAgent([])
    with pytest.raises(FileExistsError):
        generate_yaml_course([], config, GuidePromptBuilder(), agent, MarkdownWriter())
    assert not agent.calls
    assert existing.read_text() == "keep"


def test_cli_custom_template_reaches_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_spec(tmp_path, sample_spec())
    bundled = Path(__file__).parents[1] / "src/java_quickstart_generator/templates/course_prompt.md"
    custom = tmp_path / "custom.md"
    custom.write_text(
        bundled.read_text().replace(
            "Generate only the current section",
            "CUSTOM GUIDANCE: Generate only the current section",
        )
    )
    agent = CourseAgent([AgentResponse("draft", "thread")])

    def fake_agent(model: str | None) -> CourseAgent:
        return agent

    monkeypatch.setattr(cli, "CodexAgent", fake_agent)
    status = cli.main(
        [
            "SEC-01",
            "--course-spec",
            str(path),
            "--prompt-template",
            str(custom),
            "--drafts-directory",
            str(tmp_path / "drafts"),
        ]
    )
    assert status == 0
    assert "CUSTOM GUIDANCE" in agent.calls[0][0]
    assert (tmp_path / "drafts/SEC-01/01-section.md").read_text() == "draft"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("# Continuation turn", "# Continuation turn\n$course_spec"),
        ("$course_spec", ""),
        ("$purpose", "$unknown"),
        ("$topics", "$topics ${topics}"),
        ("$layout", "${layout"),
    ],
)
def test_cli_invalid_template_prevents_agent_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old: str, new: str
) -> None:
    path = write_spec(tmp_path, sample_spec())
    bundled = Path(__file__).parents[1] / "src/java_quickstart_generator/templates/course_prompt.md"
    custom = tmp_path / "bad.md"
    custom.write_text(bundled.read_text().replace(old, new))

    def forbidden_agent(model: str | None) -> CourseAgent:
        raise AssertionError("Invalid template must fail before creating an agent")

    monkeypatch.setattr(cli, "CodexAgent", forbidden_agent)
    assert (
        cli.main(
            [
                "SEC-01",
                "--course-spec",
                str(path),
                "--prompt-template",
                str(custom),
            ]
        )
        == 1
    )


@pytest.mark.parametrize("response", [AgentResponse("", "thread"), AgentResponse("ok", " ")])
def test_failed_second_response_preserves_only_completed_draft(
    tmp_path: Path, response: AgentResponse
) -> None:
    path = write_spec(tmp_path, sample_spec())
    config = GeneratorConfig(path, tmp_path / "drafts")
    agent = CourseAgent([AgentResponse("completed", "thread"), response])
    with pytest.raises(ValueError):
        generate_yaml_course([], config, GuidePromptBuilder(), agent, MarkdownWriter())
    assert len(agent.calls) == 2
    assert (config.drafts_directory / "SEC-02/01-section.md").read_text() == "completed"
    assert not (config.drafts_directory / "SEC-01").exists()
