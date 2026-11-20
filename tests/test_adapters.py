"""Offline tests for concrete adapter behavior."""

from pathlib import Path

import pytest
from openai_codex import Sandbox

import java_quickstart_generator.adapters as adapters
from java_quickstart_generator.adapters import (
    CodexAgent,
    GenerationError,
    GuidePromptBuilder,
    MarkdownWriter,
)
from java_quickstart_generator.models import (
    AgentResponse,
    GenerationRequest,
    GeneratorConfig,
    ModulePart,
)


def make_request(tmp_path: Path, thread_id: str | None = None) -> GenerationRequest:
    """Create a request whose prompt path deliberately does not exist."""

    return GenerationRequest(
        part=ModulePart(
            module_id="SEC-01",
            prompt_path=tmp_path / "missing-prompts" / "01-orientation.md",
            title="Orientation",
        ),
        instruction="UNIQUE_CURRENT_INSTRUCTION",
        thread_id=thread_id,
    )


def make_config(tmp_path: Path, guide_spec: Path) -> GeneratorConfig:
    """Create adapter configuration rooted in a temporary directory."""

    return GeneratorConfig(
        guide_spec=guide_spec,
        prompts_directory=tmp_path / "prompts" / "modules",
        drafts_directory=tmp_path / "drafts",
    )


class FakeResult:
    """Minimal stand-in for the SDK turn result."""

    def __init__(self, final_response: str | None) -> None:
        self.final_response = final_response


class FakeThread:
    """Minimal stand-in for a synchronous SDK thread."""

    def __init__(
        self,
        thread_id: str | None,
        final_response: str | None = "generated content",
        run_error: Exception | None = None,
    ) -> None:
        self.id = thread_id
        self.final_response = final_response
        self.run_error = run_error
        self.prompts: list[str] = []

    def run(self, prompt: str) -> FakeResult:
        self.prompts.append(prompt)
        if self.run_error is not None:
            raise self.run_error
        return FakeResult(self.final_response)


class FakeCodex:
    """Record SDK lifecycle and thread-selection calls."""

    def __init__(self, thread: FakeThread) -> None:
        self.thread = thread
        self.start_calls: list[tuple[str | None, Sandbox]] = []
        self.resume_calls: list[str] = []
        self.closed = False
        self.exit_exception_type: object = None

    def __enter__(self) -> "FakeCodex":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.closed = True
        self.exit_exception_type = exc_type

    def thread_start(self, *, model: str | None, sandbox: Sandbox) -> FakeThread:
        self.start_calls.append((model, sandbox))
        return self.thread

    def thread_resume(self, thread_id: str) -> FakeThread:
        self.resume_calls.append(thread_id)
        return self.thread


def install_fake_codex(
    monkeypatch: pytest.MonkeyPatch,
    thread: FakeThread,
) -> FakeCodex:
    """Replace the SDK client constructor for one offline test."""

    fake_codex = FakeCodex(thread)
    monkeypatch.setattr(adapters, "Codex", lambda: fake_codex)
    return fake_codex


def test_initial_prompt_includes_full_context_without_reading_part_path(tmp_path: Path) -> None:
    guide_spec = tmp_path / "guide-spec.md"
    guide_spec.write_text("GUIDE_SPEC_UNIQUE_MARKER", encoding="utf-8")
    request = make_request(tmp_path)

    prompt = GuidePromptBuilder().build_prompt(request, make_config(tmp_path, guide_spec))

    assert "# Initial generation contract" in prompt
    assert "## Complete guide specification" in prompt
    assert "GUIDE_SPEC_UNIQUE_MARKER" in prompt
    assert "## Current module part" in prompt
    assert "Module ID: SEC-01" in prompt
    assert "Part title: Orientation" in prompt
    assert "Prompt file: 01-orientation.md" in prompt
    assert "## Part instruction" in prompt
    assert "## Output boundary" in prompt
    assert prompt.count(request.instruction) == 1


def test_continuation_prompt_uses_capsule_without_repeating_guide_spec(tmp_path: Path) -> None:
    guide_spec = tmp_path / "guide-spec.md"
    guide_spec.write_text("GUIDE_SPEC_MUST_NOT_BE_REPEATED", encoding="utf-8")
    request = make_request(tmp_path, thread_id="existing-thread")

    prompt = GuidePromptBuilder().build_prompt(request, make_config(tmp_path, guide_spec))

    assert "# Continuation contract" in prompt
    assert "context already established in this thread" in prompt
    assert "Preserve established territory-map IDs" in prompt
    assert "Maintain continuity with previously generated parts" in prompt
    assert "## Current module part" in prompt
    assert "## Output boundary" in prompt
    assert "## Complete guide specification" not in prompt
    assert "GUIDE_SPEC_MUST_NOT_BE_REPEATED" not in prompt
    assert prompt.count(request.instruction) == 1


def test_initial_prompt_rejects_missing_guide_specification(tmp_path: Path) -> None:
    missing_guide_spec = tmp_path / "missing-guide-spec.md"

    with pytest.raises(FileNotFoundError, match="Guide specification not found"):
        GuidePromptBuilder().build_prompt(
            make_request(tmp_path),
            make_config(tmp_path, missing_guide_spec),
        )


def test_initial_prompt_rejects_empty_guide_specification(tmp_path: Path) -> None:
    empty_guide_spec = tmp_path / "guide-spec.md"
    empty_guide_spec.write_text("  \n\t", encoding="utf-8")

    with pytest.raises(ValueError, match="Guide specification is empty"):
        GuidePromptBuilder().build_prompt(
            make_request(tmp_path),
            make_config(tmp_path, empty_guide_spec),
        )


def test_writer_creates_utf8_draft_and_parent_directories(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    part = ModulePart(
        module_id="SEC-01",
        prompt_path=Path("prompts/modules/SEC-01/01-orientation.md"),
        title="Orientation",
    )
    response = AgentResponse("# Café orientation\nこんにちは\n", "thread-1")

    artifact_path = MarkdownWriter().write_artifact(part, response, config)

    expected_path = config.drafts_directory / "SEC-01" / "01-orientation.md"
    assert artifact_path == expected_path
    assert artifact_path.read_text(encoding="utf-8") == response.content
    assert artifact_path.resolve().is_relative_to(config.drafts_directory.resolve())


def test_writer_refuses_overwrite_and_preserves_existing_content(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    part = ModulePart("SEC-01", Path("01-orientation.md"), "Orientation")
    writer = MarkdownWriter()
    artifact_path = writer.write_artifact(
        part,
        AgentResponse("original content", "thread-1"),
        config,
    )

    with pytest.raises(FileExistsError):
        writer.write_artifact(
            part,
            AgentResponse("replacement content", "thread-2"),
            config,
        )

    assert artifact_path.read_text(encoding="utf-8") == "original content"


@pytest.mark.parametrize("empty_content", ["", "  \n\t"])
def test_writer_rejects_empty_content_without_creating_artifact(
    tmp_path: Path,
    empty_content: str,
) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    part = ModulePart("SEC-01", Path("01-orientation.md"), "Orientation")

    with pytest.raises(ValueError, match="Artifact content must not be empty"):
        MarkdownWriter().write_artifact(
            part,
            AgentResponse(empty_content, "thread-1"),
            config,
        )

    assert not (config.drafts_directory / "SEC-01" / "01-orientation.md").exists()


def test_writer_rejects_module_id_path_traversal(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    writer = MarkdownWriter()
    response = AgentResponse("content", "thread-1")

    for module_id in ("../outside", "safe/../../outside", str(tmp_path / "absolute-outside")):
        part = ModulePart(module_id, Path("escape.md"), "Escape")
        with pytest.raises(ValueError, match="escapes drafts directory"):
            writer.write_artifact(part, response, config)

    assert not (tmp_path / "outside" / "escape.md").exists()
    assert not (tmp_path / "absolute-outside" / "escape.md").exists()


def test_writer_uses_prompt_filename_and_ignores_title_for_output_path(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    part = ModulePart(
        module_id="SEC-01",
        prompt_path=Path("../../01-safe.md"),
        title="../../outside",
    )

    artifact_path = MarkdownWriter().write_artifact(
        part,
        AgentResponse("safe content", "thread-1"),
        config,
    )

    assert artifact_path == config.drafts_directory / "SEC-01" / "01-safe.md"
    assert artifact_path.resolve().is_relative_to(config.drafts_directory.resolve())
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("invalid_prompt_path", [Path("."), Path("..")])
def test_writer_rejects_prompt_path_without_valid_filename(
    tmp_path: Path,
    invalid_prompt_path: Path,
) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    part = ModulePart("SEC-01", invalid_prompt_path, "Invalid")

    with pytest.raises(ValueError, match="no valid filename"):
        MarkdownWriter().write_artifact(
            part,
            AgentResponse("content", "thread-1"),
            config,
        )

    assert not config.drafts_directory.exists()


def test_writer_rejects_symlink_escape_from_drafts_root(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "unused-guide.md")
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    config.drafts_directory.mkdir()
    (config.drafts_directory / "SEC-01").symlink_to(outside_directory, target_is_directory=True)
    part = ModulePart("SEC-01", Path("escape.md"), "Escape")

    with pytest.raises(ValueError, match="escapes drafts directory"):
        MarkdownWriter().write_artifact(
            part,
            AgentResponse("content", "thread-1"),
            config,
        )

    assert not (outside_directory / "escape.md").exists()


def test_codex_agent_starts_read_only_thread_with_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread = FakeThread("sdk-thread", final_response="generated Markdown")
    fake_codex = install_fake_codex(monkeypatch, thread)

    response = CodexAgent(model="configured-model").run_agent("generate this part", None)

    assert fake_codex.start_calls == [("configured-model", Sandbox.read_only)]
    assert fake_codex.resume_calls == []
    assert thread.prompts == ["generate this part"]
    assert response == AgentResponse("generated Markdown", "sdk-thread")
    assert fake_codex.closed
    assert fake_codex.exit_exception_type is None


def test_codex_agent_delegates_to_sdk_default_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_codex = install_fake_codex(monkeypatch, FakeThread("sdk-thread"))

    CodexAgent().run_agent("generate this part", None)

    assert fake_codex.start_calls == [(None, Sandbox.read_only)]


def test_codex_agent_resumes_exact_thread_without_starting_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread = FakeThread("existing-thread", final_response="continued Markdown")
    fake_codex = install_fake_codex(monkeypatch, thread)

    response = CodexAgent(model="unused-on-resume").run_agent(
        "continue this part",
        "existing-thread",
    )

    assert fake_codex.start_calls == []
    assert fake_codex.resume_calls == ["existing-thread"]
    assert thread.prompts == ["continue this part"]
    assert response == AgentResponse("continued Markdown", "existing-thread")
    assert fake_codex.closed


def test_codex_agent_rejects_different_resumed_thread_before_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread = FakeThread("wrong-thread")
    fake_codex = install_fake_codex(monkeypatch, thread)

    with pytest.raises(ValueError, match="different Codex thread ID"):
        CodexAgent().run_agent("must not run", "expected-thread")

    assert fake_codex.resume_calls == ["expected-thread"]
    assert thread.prompts == []
    assert fake_codex.closed
    assert fake_codex.exit_exception_type is ValueError


@pytest.mark.parametrize("missing_thread_id", [None, "", "  "])
def test_codex_agent_rejects_missing_resumed_thread_id_before_running(
    monkeypatch: pytest.MonkeyPatch,
    missing_thread_id: str | None,
) -> None:
    thread = FakeThread(missing_thread_id)
    fake_codex = install_fake_codex(monkeypatch, thread)

    with pytest.raises(ValueError, match="no thread ID"):
        CodexAgent().run_agent("must not run", "expected-thread")

    assert fake_codex.resume_calls == ["expected-thread"]
    assert thread.prompts == []
    assert fake_codex.closed
    assert fake_codex.exit_exception_type is ValueError


@pytest.mark.parametrize("empty_response", [None, "", "  \n\t"])
def test_codex_agent_rejects_empty_response_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    empty_response: str | None,
) -> None:
    fake_codex = install_fake_codex(
        monkeypatch,
        FakeThread("sdk-thread", final_response=empty_response),
    )

    with pytest.raises(ValueError, match="empty final response"):
        CodexAgent().run_agent("generate this part", None)

    assert fake_codex.closed
    assert fake_codex.exit_exception_type is ValueError


@pytest.mark.parametrize("missing_thread_id", [None, "", "  "])
def test_codex_agent_rejects_missing_thread_id_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    missing_thread_id: str | None,
) -> None:
    fake_codex = install_fake_codex(monkeypatch, FakeThread(missing_thread_id))

    with pytest.raises(ValueError, match="no thread ID"):
        CodexAgent().run_agent("generate this part", None)

    assert fake_codex.closed
    assert fake_codex.exit_exception_type is ValueError


def test_codex_agent_translates_thread_run_failure_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_error = RuntimeError("turn failed")
    fake_codex = install_fake_codex(
        monkeypatch,
        FakeThread("sdk-thread", run_error=sdk_error),
    )

    with pytest.raises(GenerationError, match="Codex turn failed: turn failed") as error_info:
        CodexAgent().run_agent("generate this part", None)

    assert error_info.value.__cause__ is sdk_error
    assert fake_codex.closed
    assert fake_codex.exit_exception_type is GenerationError
