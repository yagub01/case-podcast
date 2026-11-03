"""Claude calls: study brief, episode script, and fact check."""

import base64
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
WORDS_PER_MINUTE = 150
COURSES_DIR = Path(__file__).parent / "courses"
HOST_A, HOST_B = "MAYA", "DANIEL"

# Kept identical across all calls so the document prefix is served from cache.
SYSTEM = (
    "You help an MBA student prepare for case-method classes and learn from documents "
    "by writing study briefs and audio episode scripts. Be exact with facts and figures "
    "from the source. Never invent numbers, names, or events that the source does not "
    "contain; when something is uncertain, say so."
)


class PipelineError(Exception):
    pass


@dataclass
class Course:
    name: str
    filename: str
    text: str


@dataclass
class Source:
    name: str
    pdf_bytes: bytes | None = None
    text: str | None = None

    def block(self) -> dict:
        if self.pdf_bytes:
            source = {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(self.pdf_bytes).decode(),
            }
        else:
            source = {"type": "text", "media_type": "text/plain", "data": self.text}
        return {
            "type": "document",
            "source": source,
            "title": self.name,
            "cache_control": {"type": "ephemeral"},
        }


def load_courses() -> list[Course]:
    courses = []
    for path in sorted(COURSES_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^#\s*Course:\s*(.+)$", text, re.MULTILINE)
        courses.append(Course(match.group(1).strip() if match else path.stem, path.name, text))
    return courses


def _ask(prefix: list[dict], instructions: str, effort: str = "high") -> str:
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prefix + [{"type": "text", "text": instructions}]}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise PipelineError("Claude declined this request. Try a different document.")
    if message.stop_reason == "max_tokens":
        raise PipelineError("The response was cut off. Try a shorter episode length.")
    return "".join(b.text for b in message.content if b.type == "text").strip()


def _prefix(source: Source, courses: list[Course]) -> list[dict]:
    blocks = []
    if courses:
        profiles = "\n\n".join(
            f'<course_profile file="{c.filename}">\n{c.text}\n</course_profile>' for c in courses
        )
        blocks.append({"type": "text", "text": f"<course_profiles>\n{profiles}\n</course_profiles>"})
    blocks.append(source.block())
    return blocks


CASE_BRIEF = """The document above is a business school case.

{course_instruction}
{assignment_block}
Write a prep brief in Markdown with exactly these sections:

## Course and session
The course and session this case belongs to, and the one or two concepts the session is meant to teach. Name the matched course profile and session and give the reason for the match in one or two sentences.

## The situation
The protagonist, the organization, the decision to be made, and the time pressure, in one short paragraph.

## Fact sheet
Every fact a student needs to speak credibly in class: key figures from the text and the exhibits (with units and years), dates, people and their roles, market and competitor data, financials, and the options under consideration. Group the bullets by theme and cite exhibit numbers. Include only facts the case states. Label any figure you calculate as a calculation and show how you got it.

## Likely discussion questions
The probable opening cold-call question, then 5 to 8 questions the professor is likely to ask, in the order a class discussion would usually follow. Give a short, strong answer to each, supported by facts from the fact sheet.

## Analysis
Apply the course frameworks that fit this session, with the key calculations.

## Positions
The strongest argument for each option, then a recommended position the student could defend in class, with the facts that support it best.

## Contributions to make in class
Non-obvious insights, common traps, and comments that would add to the discussion.
"""

GENERAL_BRIEF = """Write a study brief of the document above in Markdown with exactly these sections:

## Overview
What the document is and what it is about, in one short paragraph.

## Fact sheet
The key facts, figures (with units and dates), names, and definitions, as bullets grouped by theme. Include only what the document states.

## Main ideas
The central arguments or lessons and how they connect.

## Questions to test understanding
5 to 8 questions with short answers.
{focus_block}"""

SCRIPT = """Using the document above and the brief below, write the script for an audio episode of about {minutes} minutes (roughly {words} words).

{format_instructions}

Requirements:
- Cover every fact-sheet item that matters for understanding or discussing the material. Say numbers the way a person would say them aloud.
- {structure}
- Write for listening: short sentences and clear transitions. No Markdown, headings, bullet points, stage directions, or sound effects.
- Do not add facts that are not in the document.

Output only the script.

<brief>
{brief}
</brief>
"""

TWO_HOSTS = (
    f"The episode has two hosts, {HOST_A} and {HOST_B}. {HOST_A} leads and explains the material. "
    f"{HOST_B} asks the questions a sharp classmate would ask, pushes back on weak reasoning, and "
    "summarizes key points. Begin every turn on a new line with the speaker's name in capitals "
    f"and a colon, for example \"{HOST_A}: ...\". Keep each turn to a few sentences."
)
NARRATOR = (
    "The episode has a single narrator speaking directly to the listener. "
    "Write plain paragraphs with no speaker labels."
)
CASE_STRUCTURE = (
    "Open with the decision the protagonist faces. Walk through the facts, then work through the "
    "likely discussion questions and the main positions. Close with a recommended position and "
    "the facts to remember for class."
)
GENERAL_STRUCTURE = (
    "Open with why the material matters, explain the main ideas with the supporting facts, and "
    "close with a short recap of the points to remember."
)

CHECK = """Below are a brief and a draft script for an audio episode about the document above.

Revise the draft against the brief's fact sheet and the document:
- Add any important fact, figure, or option from the fact sheet that the draft leaves out, worked naturally into the script.
- Correct any figure, name, or date that does not match the document.
- Remove anything the document does not support.

Keep the same format and speaker labels. The length may grow by up to 15 percent.

Output only the complete revised script.

<brief>
{brief}
</brief>

<draft_script>
{draft}
</draft_script>
"""


def make_brief(
    source: Source,
    courses: list[Course],
    case_mode: bool,
    auto_detect: bool = True,
    assignment_questions: str = "",
    focus: str = "",
) -> str:
    if not case_mode:
        focus_block = (
            f"\nThe student wants the brief to focus on: {focus.strip()}\n" if focus.strip() else ""
        )
        return _ask(_prefix(source, []), GENERAL_BRIEF.format(focus_block=focus_block))

    if not courses:
        course_instruction = (
            "No course profiles are available. Infer the most likely course topic and teaching purpose."
        )
    elif auto_detect:
        course_instruction = (
            "The course profiles above describe the student's courses. Identify the course and "
            "session this case belongs to. If no profile fits well, say so and infer the most "
            "likely teaching purpose."
        )
    else:
        course_instruction = (
            "The course profile above is the course this case is assigned in. Identify the session."
        )

    assignment_block = ""
    if assignment_questions.strip():
        assignment_block = (
            "\nThe professor assigned these questions. Answer each one first in the "
            f"'Likely discussion questions' section, before adding your own:\n{assignment_questions.strip()}\n"
        )

    instructions = CASE_BRIEF.format(
        course_instruction=course_instruction, assignment_block=assignment_block
    )
    return _ask(_prefix(source, courses), instructions)


def write_script(
    source: Source, courses: list[Course], case_mode: bool, brief: str, two_hosts: bool, minutes: int
) -> str:
    instructions = SCRIPT.format(
        minutes=minutes,
        words=minutes * WORDS_PER_MINUTE,
        format_instructions=TWO_HOSTS if two_hosts else NARRATOR,
        structure=CASE_STRUCTURE if case_mode else GENERAL_STRUCTURE,
        brief=brief,
    )
    return _ask(_prefix(source, courses if case_mode else []), instructions)


def check_script(source: Source, courses: list[Course], case_mode: bool, brief: str, draft: str) -> str:
    instructions = CHECK.format(brief=brief, draft=draft)
    return _ask(_prefix(source, courses if case_mode else []), instructions)
