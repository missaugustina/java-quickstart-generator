"""Offline tests for generation workflow coordination."""

from pathlib import Path

import pytest

from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)
from java_quickstart_generator.workflow import generate_course, generate_module, generate_part


class FakePromptBuilder:
    """Record prompt-building inputs and return predictable text."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[tuple[GenerationRequest, GeneratorConfig]] = []

    def build_prompt(
        self,
        request: GenerationRequest,
        config: GeneratorConfig,
    ) -> str:
        self.events.append("build_prompt")
        self.calls.append((request, config))
        return "constructed prompt"


class FakeAgent:
    """Record agent inputs and return a configured response."""

    def __init__(self, response: AgentResponse, events: list[str]) -> None:
        self.response = response
        self.events = events
        self.calls: list[tuple[str, str | None]] = []

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        self.events.append("run_agent")
        self.calls.append((prompt, thread_id))
        return self.response


class FakeWriter:
    """Record artifact-writing inputs and return a configured path."""

    def __init__(self, artifact_path: Path, events: list[str]) -> None:
        self.artifact_path = artifact_path
        self.events = events
        self.calls: list[tuple[ModulePart, AgentResponse, GeneratorConfig]] = []

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path:
        self.events.append("write_artifact")
        self.calls.append((part, response, config))
        return self.artifact_path


class SequencedFakeAgent:
    """Return ordered responses and optionally fail on a selected call."""

    def __init__(
        self,
        responses: list[AgentResponse],
        events: list[str],
        fail_on_call: int | None = None,
    ) -> None:
        self.responses = responses
        self.events = events
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, str | None]] = []

    def run_agent(self, prompt: str, thread_id: str | None) -> AgentResponse:
        self.events.append("run_agent")
        self.calls.append((prompt, thread_id))
        call_number = len(self.calls)

        if call_number == self.fail_on_call:
            raise RuntimeError(f"Agent failed on call {call_number}")

        try:
            return self.responses[call_number - 1]
        except IndexError as error:
            raise AssertionError(f"No fake response configured for call {call_number}") from error


class RecordingWriter:
    """Write predictable temporary drafts while recording workflow inputs."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[tuple[ModulePart, AgentResponse, GeneratorConfig]] = []

    def write_artifact(
        self,
        part: ModulePart,
        response: AgentResponse,
        config: GeneratorConfig,
    ) -> Path:
        self.events.append("write_artifact")
        self.calls.append((part, response, config))
        artifact_path = config.drafts_directory / part.module_id / part.prompt_path.name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(response.content, encoding="utf-8")
        return artifact_path


def make_request(thread_id: str | None = None) -> tuple[GenerationRequest, GeneratorConfig]:
    """Create predictable workflow inputs for one module part."""

    part = ModulePart(
        module_id="SEC-01",
        prompt_path=Path("prompts/modules/SEC-01/01-orientation.md"),
        title="Orientation",
    )
    request = GenerationRequest(
        part=part,
        instruction="Generate the orientation section.",
        thread_id=thread_id,
    )
    config = GeneratorConfig(
        guide_spec=Path("prompts/guide-spec.md"),
        prompts_directory=Path("prompts/modules"),
        drafts_directory=Path("drafts"),
    )
    return request, config


def make_module_config(tmp_path: Path) -> GeneratorConfig:
    """Create temporary project paths for module workflow tests."""

    prompts_directory = tmp_path / "prompts" / "modules"
    prompts_directory.mkdir(parents=True)
    return GeneratorConfig(
        guide_spec=tmp_path / "prompts" / "guide-spec.md",
        prompts_directory=prompts_directory,
        drafts_directory=tmp_path / "drafts",
    )


def test_generate_part_coordinates_roles_and_returns_outcome() -> None:
    events: list[str] = []
    request, config = make_request()
    response = AgentResponse(content="# Orientation", thread_id="thread-created")
    artifact_path = Path("drafts/SEC-01/01-orientation.md")
    prompt_builder = FakePromptBuilder(events)
    agent = FakeAgent(response, events)
    writer = FakeWriter(artifact_path, events)

    outcome = generate_part(request, config, prompt_builder, agent, writer)

    assert events == ["build_prompt", "run_agent", "write_artifact"]
    assert prompt_builder.calls == [(request, config)]
    assert agent.calls == [("constructed prompt", None)]
    assert writer.calls == [(request.part, response, config)]
    assert outcome.part == request.part
    assert outcome.artifact_path == artifact_path
    assert outcome.thread_id == "thread-created"


def test_generate_part_passes_no_thread_id_for_first_turn() -> None:
    events: list[str] = []
    request, config = make_request()
    agent = FakeAgent(AgentResponse("content", "new-thread"), events)

    generate_part(
        request,
        config,
        FakePromptBuilder(events),
        agent,
        FakeWriter(Path("draft.md"), events),
    )

    assert agent.calls == [("constructed prompt", None)]


def test_generate_part_passes_existing_thread_id_for_resumed_turn() -> None:
    events: list[str] = []
    request, config = make_request(thread_id="existing-thread")
    agent = FakeAgent(AgentResponse("content", "existing-thread"), events)

    generate_part(
        request,
        config,
        FakePromptBuilder(events),
        agent,
        FakeWriter(Path("draft.md"), events),
    )

    assert agent.calls == [("constructed prompt", "existing-thread")]


@pytest.mark.parametrize("empty_content", ["", "   \n\t"])
def test_generate_part_rejects_empty_content_before_writing(empty_content: str) -> None:
    events: list[str] = []
    request, config = make_request()
    writer = FakeWriter(Path("must-not-exist.md"), events)

    with pytest.raises(ValueError, match="empty response"):
        generate_part(
            request,
            config,
            FakePromptBuilder(events),
            FakeAgent(AgentResponse(empty_content, "thread-created"), events),
            writer,
        )

    assert events == ["build_prompt", "run_agent"]
    assert writer.calls == []


def test_generate_module_orders_prompts_filters_files_and_preserves_thread(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_directory = config.prompts_directory / "SEC-01"
    module_directory.mkdir()
    (module_directory / "03-practice.md").write_text("third instruction", encoding="utf-8")
    (module_directory / "01-orientation.md").write_text("first instruction", encoding="utf-8")
    (module_directory / "02-concepts.md").write_text("second instruction", encoding="utf-8")
    (module_directory / "notes.txt").write_text("ignore this", encoding="utf-8")
    nested_directory = module_directory / "00-nested.md"
    nested_directory.mkdir()
    (nested_directory / "prompt.md").write_text("ignore this too", encoding="utf-8")
    prompt_builder = FakePromptBuilder(events)
    agent = SequencedFakeAgent(
        [
            AgentResponse("first draft", "course-thread"),
            AgentResponse("second draft", "course-thread"),
            AgentResponse("third draft", "course-thread"),
        ],
        events,
    )
    writer = RecordingWriter(events)

    outcomes = generate_module("SEC-01", config, prompt_builder, agent, writer)

    requests = [request for request, _config in prompt_builder.calls]
    assert [request.part.prompt_path.name for request in requests] == [
        "01-orientation.md",
        "02-concepts.md",
        "03-practice.md",
    ]
    assert [request.instruction for request in requests] == [
        "first instruction",
        "second instruction",
        "third instruction",
    ]
    assert [request.thread_id for request in requests] == [None, "course-thread", "course-thread"]
    assert agent.calls == [
        ("constructed prompt", None),
        ("constructed prompt", "course-thread"),
        ("constructed prompt", "course-thread"),
    ]
    assert [call[0].prompt_path.name for call in writer.calls] == [
        "01-orientation.md",
        "02-concepts.md",
        "03-practice.md",
    ]
    assert [outcome.thread_id for outcome in outcomes] == ["course-thread"] * 3
    assert [outcome.artifact_path.name for outcome in outcomes] == [
        "01-orientation.md",
        "02-concepts.md",
        "03-practice.md",
    ]


def test_generate_module_rejects_missing_directory_before_calling_roles(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    prompt_builder = FakePromptBuilder(events)
    agent = SequencedFakeAgent([], events)
    writer = RecordingWriter(events)

    with pytest.raises(FileNotFoundError, match="Module prompt directory not found"):
        generate_module("SEC-99", config, prompt_builder, agent, writer)

    assert events == []
    assert prompt_builder.calls == []
    assert agent.calls == []
    assert writer.calls == []


def test_generate_module_rejects_parent_directory_traversal(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="must not contain parent-directory traversal"):
        generate_module(
            "../outside",
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_rejects_absolute_module_id(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (outside_directory / "01-prompt.md").write_text("outside prompt", encoding="utf-8")
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="must be a relative path"):
        generate_module(
            str(outside_directory),
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_rejects_module_symlink_outside_prompts_root(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (outside_directory / "01-prompt.md").write_text("outside prompt", encoding="utf-8")
    (config.prompts_directory / "SEC-01").symlink_to(outside_directory, target_is_directory=True)
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="must remain inside the prompts directory"):
        generate_module(
            "SEC-01",
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_rejects_symlinked_markdown_prompt(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_directory = config.prompts_directory / "SEC-01"
    module_directory.mkdir()
    outside_prompt = tmp_path / "outside.md"
    outside_prompt.write_text("outside prompt", encoding="utf-8")
    (module_directory / "01-prompt.md").symlink_to(outside_prompt)
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        generate_module(
            "SEC-01",
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_rejects_directory_without_prompt_files(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_directory = config.prompts_directory / "SEC-01"
    module_directory.mkdir()
    (module_directory / "notes.txt").write_text("not a prompt", encoding="utf-8")
    nested_directory = module_directory / "nested"
    nested_directory.mkdir()
    (nested_directory / "prompt.md").write_text("nested prompt", encoding="utf-8")
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="no Markdown prompt files"):
        generate_module(
            "SEC-01",
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_rejects_empty_prompt_before_calling_roles(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_directory = config.prompts_directory / "SEC-01"
    module_directory.mkdir()
    (module_directory / "01-empty.md").write_text("  \n\t", encoding="utf-8")
    agent = SequencedFakeAgent([], events)

    with pytest.raises(ValueError, match="Prompt file is empty"):
        generate_module(
            "SEC-01",
            config,
            FakePromptBuilder(events),
            agent,
            RecordingWriter(events),
        )

    assert events == []
    assert agent.calls == []


def test_generate_module_stops_after_failure_and_preserves_earlier_draft(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_directory = config.prompts_directory / "SEC-01"
    module_directory.mkdir()
    for number in range(1, 4):
        (module_directory / f"0{number}-part.md").write_text(
            f"instruction {number}",
            encoding="utf-8",
        )
    prompt_builder = FakePromptBuilder(events)
    agent = SequencedFakeAgent(
        [AgentResponse("completed first draft", "thread-1")],
        events,
        fail_on_call=2,
    )
    writer = RecordingWriter(events)

    with pytest.raises(RuntimeError, match="Agent failed on call 2"):
        generate_module("SEC-01", config, prompt_builder, agent, writer)

    requests = [request for request, _config in prompt_builder.calls]
    assert [request.part.prompt_path.name for request in requests] == [
        "01-part.md",
        "02-part.md",
    ]
    assert agent.calls == [
        ("constructed prompt", None),
        ("constructed prompt", "thread-1"),
    ]
    assert [call[0].prompt_path.name for call in writer.calls] == ["01-part.md"]
    first_draft = config.drafts_directory / "SEC-01" / "01-part.md"
    assert first_draft.read_text(encoding="utf-8") == "completed first draft"
    assert not (config.drafts_directory / "SEC-01" / "02-part.md").exists()
    assert not (config.drafts_directory / "SEC-01" / "03-part.md").exists()


def test_generate_course_preserves_one_thread_across_modules(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_one = config.prompts_directory / "SEC-01"
    module_two = config.prompts_directory / "SEC-02"
    module_one.mkdir()
    module_two.mkdir()
    (module_one / "01-map.md").write_text("map instruction", encoding="utf-8")
    (module_one / "02-concepts.md").write_text("concept instruction", encoding="utf-8")
    (module_two / "01-practice.md").write_text("practice instruction", encoding="utf-8")
    prompt_builder = FakePromptBuilder(events)
    agent = SequencedFakeAgent(
        [
            AgentResponse("map draft", "course-thread"),
            AgentResponse("concept draft", "course-thread"),
            AgentResponse("practice draft", "course-thread"),
        ],
        events,
    )

    outcomes = generate_course(
        ["SEC-01", "SEC-02"],
        config,
        prompt_builder,
        agent,
        RecordingWriter(events),
    )

    requests = [request for request, _config in prompt_builder.calls]
    assert [request.part.module_id for request in requests] == ["SEC-01", "SEC-01", "SEC-02"]
    assert [request.thread_id for request in requests] == [None, "course-thread", "course-thread"]
    assert agent.calls == [
        ("constructed prompt", None),
        ("constructed prompt", "course-thread"),
        ("constructed prompt", "course-thread"),
    ]
    assert [outcome.thread_id for outcome in outcomes] == ["course-thread"] * 3


def test_generate_course_stops_when_thread_id_changes_between_modules(tmp_path: Path) -> None:
    events: list[str] = []
    config = make_module_config(tmp_path)
    module_one = config.prompts_directory / "SEC-01"
    module_two = config.prompts_directory / "SEC-02"
    module_one.mkdir()
    module_two.mkdir()
    (module_one / "01-map.md").write_text("map instruction", encoding="utf-8")
    (module_two / "01-concepts.md").write_text("concept instruction", encoding="utf-8")
    (module_two / "02-practice.md").write_text("practice instruction", encoding="utf-8")
    agent = SequencedFakeAgent(
        [
            AgentResponse("map draft", "course-thread"),
            AgentResponse("concept draft", "different-thread"),
            AgentResponse("must not run", "course-thread"),
        ],
        events,
    )
    writer = RecordingWriter(events)

    with pytest.raises(ValueError, match="different Codex thread ID"):
        generate_course(
            ["SEC-01", "SEC-02"],
            config,
            FakePromptBuilder(events),
            agent,
            writer,
        )

    assert agent.calls == [
        ("constructed prompt", None),
        ("constructed prompt", "course-thread"),
    ]
    assert [call[0].module_id for call in writer.calls] == ["SEC-01"]
    assert (config.drafts_directory / "SEC-01" / "01-map.md").exists()
    assert not (config.drafts_directory / "SEC-02" / "01-concepts.md").exists()
    assert not (config.drafts_directory / "SEC-02" / "02-practice.md").exists()
