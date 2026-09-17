"""The explanations count as part of the code.

Since Tuesday a person has been asking you what your lines do. From today the
suite asks instead -- which is the same move you made on Thursday morning when
you stopped re-running the script by hand and wrote a test for it.

This test fails while any `# Your answer:` prompt is still empty. It does not
judge what you wrote; a facilitator does that. It only refuses to let an
unexplained line ship.
"""

from __future__ import annotations

from pathlib import Path

#: Written by the handout under every prompt. Do not reword it.
ANSWER_MARKER = "# Your answer:"

#: Characters of prose below the marker before it counts as answered.
MIN_ANSWER_CHARS = 40

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_GLOBS = ("src/**/*.py", "dashboard/**/*.py", "tests/**/*.py")


def _question_above(lines: list[str], marker_index: int) -> str:
    """Reassemble the question above an answer marker, unwrapping it."""
    start = None
    for index in range(marker_index - 1, -1, -1):
        stripped = lines[index].strip()
        if not stripped.startswith("#"):
            break
        if "TODO(EXPLAIN)" in stripped:
            start = index
            break
    if start is None:
        return "(prompt not found)"

    parts = [lines[start].split("TODO(EXPLAIN):", 1)[-1].strip()]
    for line in lines[start + 1 : marker_index]:
        text = line.strip().lstrip("#").strip()
        if not text or text.startswith("Two or three sentences"):
            break
        parts.append(text)
    return " ".join(parts)


def _unanswered(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings = []

    for number, line in enumerate(lines, start=1):
        # A prompt is a comment. The identical text inside a string literal is
        # this file defining the marker, not a prompt -- without this guard the
        # test reports itself and the finished project never goes green.
        stripped = line.strip()
        if not stripped.startswith("#") or ANSWER_MARKER not in stripped:
            continue

        answer = []
        for following in lines[number:]:
            text = following.strip()
            if not text.startswith("#"):
                break
            answer.append(text.lstrip("#").strip())

        if len("".join(answer)) < MIN_ANSWER_CHARS:
            question = _question_above(lines, number - 1)
            findings.append(
                f"{path.relative_to(PROJECT_ROOT).as_posix()}:{number} -- {question}"
            )

    return findings


def test_every_explanation_prompt_is_answered() -> None:
    """No unanswered TODO(EXPLAIN) may remain anywhere in the project.

    If this passes in a repository that never had any prompts, it is telling
    you the truth: there was nothing to explain.
    """
    open_prompts: list[str] = []
    for pattern in SEARCH_GLOBS:
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            if "__pycache__" in path.parts:
                continue
            open_prompts += _unanswered(path)

    assert not open_prompts, "explanations still missing:\n  " + "\n  ".join(open_prompts)
