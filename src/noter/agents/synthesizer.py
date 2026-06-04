import json
import logging
from json import JSONDecodeError

import anthropic
from pydantic import ValidationError

from noter.config import SYNTHESIZER_MODEL
from noter.exceptions import SynthesizerError
from noter.schemas import NoteSpec, PlannerOutput, SourceResult, SynthesizedNote

logger = logging.getLogger(__name__)

_TOKEN_LIMIT_PER_SOURCE = 3000
_WORDS_PER_TOKEN = 1.3
_WORD_LIMIT = int(_TOKEN_LIMIT_PER_SOURCE / _WORDS_PER_TOKEN)  # ~2307

_SYSTEM_PROMPT = """\
You are a research synthesizer. Given a research plan and source documents, \
produce a structured note.

Rules:
- Only synthesize information present in the provided sources — do not invent content.
- Follow the focus instruction for this note exactly.
- Eliminate redundancy across sources.
- If sources contain insufficient information for this note, respond with the literal string: null

Respond with a single valid JSON object — no markdown, no explanation, just JSON.

Schema:
{
  "note_title": "<title>",
  "core_concept": "<introductory paragraph>",
  "subtopics": [
    {"title": "<subtopic title>", "content": "<synthesized content>"}
  ],
  "sources_used": [
    {"url": "<url>", "title": "<title>"}
  ]
}
"""


def _truncate(content: str) -> str:
    words = content.split()
    return " ".join(words[:_WORD_LIMIT]) if len(words) > _WORD_LIMIT else content


def _word_overlap(a: str, b: str) -> int:
    return len(set(a.lower().split()) & set(b.lower().split()))


def _select_sources(note_spec: NoteSpec, sources: list[SourceResult]) -> list[SourceResult]:
    user = [s for s in sources if s.source == "user"]
    auto = sorted(
        [s for s in sources if s.source == "auto"],
        key=lambda s: _word_overlap(note_spec.focus, s.title + " " + s.content[:500]),
        reverse=True,
    )
    return user + auto


def _build_user_message(note_spec: NoteSpec, sources: list[SourceResult]) -> str:
    selected = _select_sources(note_spec, sources)
    parts = [f"Note to synthesize:\n{json.dumps(note_spec.model_dump(), indent=2)}\n\nSources:\n"]
    for i, src in enumerate(selected, 1):
        parts.append(f"--- Source {i}: {src.title} ({src.url}) ---\n{_truncate(src.content)}\n")
    return "".join(parts)


def _parse_response(raw: str) -> SynthesizedNote | None:
    raw = raw.strip()
    if raw.lower() == "null":
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return SynthesizedNote.model_validate(json.loads(raw))


def run(plan: PlannerOutput, sources: list[SourceResult]) -> list[SynthesizedNote]:
    client = anthropic.Anthropic()
    results = []

    for note_spec in plan.notes:
        user_message = _build_user_message(note_spec, sources)
        logger.debug(
            "Synthesizer: note %r, %d candidate source(s), prompt ~%d chars",
            note_spec.title,
            len(sources),
            len(user_message),
        )
        synthesized = None

        for attempt in range(2):
            message = client.messages.create(
                model=SYNTHESIZER_MODEL,
                max_tokens=8192,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            block = message.content[0]
            if not isinstance(block, anthropic.types.TextBlock):
                raise SynthesizerError(f"Unexpected content block type: {type(block).__name__}")
            raw = block.text
            try:
                synthesized = _parse_response(raw)
                break
            except (JSONDecodeError, ValidationError) as exc:
                if attempt == 1:
                    raise SynthesizerError(
                        f"Synthesizer returned invalid output for '{note_spec.title}' "
                        f"after 2 attempts: {exc}"
                    ) from exc
                logger.debug(
                    "Synthesizer: note %r attempt %d failed, retrying: %s",
                    note_spec.title,
                    attempt + 1,
                    exc,
                )

        if synthesized is not None:
            results.append(synthesized)
        else:
            logger.warning(
                "Synthesizer: insufficient source content for note %r — skipping", note_spec.title
            )

    return results
