"""Claude calls: study brief, episode script, and fact check."""

import base64
from dataclasses import dataclass

import anthropic

MODEL = "claude-sonnet-5-5"
EFFORT = "medium"  # the same for every call, so the document stays in the prompt cache
WORDS_PER_MINUTE = 150
HOST_A, HOST_B = "MAYA", "DANIEL"

SYSTEM = (
    "You help a student understand documents and prepare for class discussion by writing "
    "study briefs and audio episode scripts. Be exact with facts and figures from the source. "
    "Never invent numbers, names, or events that the source does not contain; when something "
    "is uncertain, say so."
)


class PipelineError(Exception):
    pass


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


def _ask(source: Source, instructions: str) -> str:
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": [source.block(), {"type": "text", "text": instructions}],
        }],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise PipelineError("Claude declined this request. Try a different document.")
    if message.stop_reason == "max_tokens":
        raise PipelineError("The response was cut off. Try a shorter episode length.")
    return "".join(b.text for b in message.content if b.type == "text").strip()


def _description_block(description: str) -> str:
    if not description.strip():
        return ""
    return (
        "The student describes the document and what they want from it below. Use this to set "
        "the focus, but take every fact from the document.\n"
        f"<description>\n{description.strip()}\n</description>\n"
    )


def _word_range(minutes: int) -> tuple[int, int, int]:
    words = minutes * WORDS_PER_MINUTE
    return words, round(words * 0.9), round(words * 1.1)


BRIEF = """Write a study brief of the document above in Markdown.
{description_block}
Begin with this section:

## What this is and what it teaches
What kind of document this is, its subject, and the one to three ideas it is meant to teach or argue. For a teaching case, infer what the instructor most likely wants students to learn from it and name the concepts or frameworks the case exercises.

If the document is a teaching case (a business school case or similar), continue with these sections:

## The situation
The protagonist, the organization, the decision to be made, and the time pressure, in one short paragraph.

## Fact sheet
Every fact a student needs to speak credibly in class: key figures from the text and the exhibits (with units and years), dates, people and their roles, market and competitor data, financials, and the options under consideration. Group the bullets by theme and cite exhibit numbers. Include only facts the document states. Label any figure you calculate as a calculation and show how you got it.

## Likely discussion questions
The probable opening cold-call question, then 5 to 8 questions an instructor is likely to ask, in the order a class discussion would usually follow. Give a short, strong answer to each, supported by facts from the fact sheet.

## Analysis
Apply the concepts the case is built to teach, with the key calculations.

## Positions
The strongest argument for each option, then a recommended position the student could defend in class, with the facts that support it best.

## Contributions to make in class
Non-obvious insights, common traps, and comments that would add to the discussion.

For any other document, continue with these sections:

## Fact sheet
The key facts, figures (with units and dates), names, and definitions, as bullets grouped by theme. Include only what the document states.

## Main ideas
The central arguments or lessons and how they connect.

## Questions to test understanding
5 to 8 questions with short answers.
"""

SCRIPT = """Using the document above and the brief below, write the script for an audio episode of about {minutes} minutes.
{description_block}
{format_instructions}

Requirements:
- Length: between {low} and {high} words. Cover what matters most first. Leave out lower-priority detail rather than exceed the limit.
- Cover the fact-sheet items that matter most for understanding or discussing the material. Say numbers the way a person would say them aloud.
- If the brief is for a teaching case, open with the decision the protagonist faces, walk through the facts, work through the likely discussion questions and the main positions, and close with a recommended position and the facts to remember for class. Otherwise, open with why the material matters, explain the main ideas with the supporting facts, and close with a short recap of the points to remember.
- Start directly with the subject. Do not comment on the brief, on any course, or on how the material was prepared.
- Write for listening: short sentences and clear transitions. No Markdown, headings, bullet points, stage directions, or sound effects.
- Do not add facts that are not in the document.

Output only the script.

<brief>
{brief}
</brief>
"""

TWO_HOSTS = (
    f"The episode has two hosts, {HOST_A} and {HOST_B}, who share the work of explaining and "
    f"analyzing. Both bring facts and arguments. {HOST_B} also pushes back on weak reasoning and "
    "asks the questions a sharp classmate would ask. Neither host speaks more than about 60 percent "
    "of the words. Keep each turn under about 80 words. Begin every turn on a new line with the "
    f"speaker's name in capitals and a colon, for example \"{HOST_A}: ...\"."
)
NARRATOR = (
    "The episode has a single narrator speaking directly to the listener. "
    "Write plain paragraphs with no speaker labels."
)

CHECK = """Below are a brief and a draft script for an audio episode about the document above.

Revise the draft against the brief's fact sheet and the document:
- Add any important fact, figure, or option from the fact sheet that the draft leaves out, worked naturally into the script.
- Correct any figure, name, or date that does not match the document.
- Remove anything the document does not support.

Keep the format, the speaker labels, and the balance between speakers. The revised script must be between {low} and {high} words. If adding a missing fact would push it over, cut lower-priority detail to make room.

Output only the complete revised script.

<brief>
{brief}
</brief>

<draft_script>
{draft}
</draft_script>
"""


def make_brief(source: Source, description: str = "") -> str:
    return _ask(source, BRIEF.format(description_block=_description_block(description)))


def write_script(source: Source, brief: str, description: str, two_hosts: bool, minutes: int) -> str:
    _, low, high = _word_range(minutes)
    instructions = SCRIPT.format(
        minutes=minutes,
        low=low,
        high=high,
        description_block=_description_block(description),
        format_instructions=TWO_HOSTS if two_hosts else NARRATOR,
        brief=brief,
    )
    return _ask(source, instructions)


def check_script(source: Source, brief: str, draft: str, minutes: int) -> str:
    _, low, high = _word_range(minutes)
    return _ask(source, CHECK.format(low=low, high=high, brief=brief, draft=draft))
