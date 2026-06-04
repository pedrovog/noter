import json
import logging
import re
import unicodedata
from datetime import date
from json import JSONDecodeError
from pathlib import Path

import anthropic

from noter.config import WRITER_MODEL
from noter.exceptions import WriterError
from noter.schemas import SynthesizedNote

logger = logging.getLogger(__name__)

_TAG_SYSTEM_PROMPT = """\
Infer 3 to 5 concise, lowercase tags for an Obsidian note based on its title and \
core concept.

Respond with a single valid JSON array of strings — no markdown, no explanation, \
just JSON.

Example: ["machine-learning", "neural-networks", "backpropagation"]
"""


def _sanitize(title: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^\w\s-]", "", ascii_)
    name = re.sub(r"\s+", " ", clean).strip()
    if not name:
        raise WriterError(f"Title '{title}' produces an empty filename after sanitization")
    return name


def _resolve_path(inbox: Path, name: str) -> Path:
    path = inbox / f"{name}.md"
    n = 2
    while path.exists():
        path = inbox / f"{name} ({n}).md"
        n += 1
    return path


def _infer_tags(note: SynthesizedNote, client: anthropic.Anthropic) -> list[str]:
    user_content = f"Title: {note.note_title}\nCore concept: {note.core_concept}"
    for attempt in range(2):
        message = client.messages.create(
            model=WRITER_MODEL,
            max_tokens=256,
            system=_TAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        block = message.content[0]
        if not isinstance(block, anthropic.types.TextBlock):
            raise WriterError(f"Unexpected content block type: {type(block).__name__}")
        raw = block.text
        try:
            tags = json.loads(raw.strip())
            if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
                return tags
            raise ValueError(f"unexpected tag format: {tags}")
        except (JSONDecodeError, ValueError) as exc:
            if attempt == 1:
                raise WriterError(f"Failed to infer tags for '{note.note_title}': {exc}") from exc
            logger.debug(
                "Writer: tag inference for %r attempt %d failed, retrying: %s",
                note.note_title,
                attempt + 1,
                exc,
            )
    return []  # unreachable; satisfies type checker


def _yaml_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render_note(note: SynthesizedNote, tags: list[str], created: str) -> str:
    tags_str = ", ".join(tags)
    sources_yaml = "\n".join(
        f'  - url: "{_yaml_str(s.url)}"\n    title: "{_yaml_str(s.title)}"'
        for s in note.sources_used
    )
    subtopics_md = "\n\n".join(f"### {st.title}\n\n{st.content}" for st in note.subtopics)
    sources_list = "\n".join(
        f"- [{s.title.replace(']', r'\]')}]({s.url})" for s in note.sources_used
    )
    return (
        f"---\n"
        f"type: permanent\n"
        f"created: {created}\n"
        f"tags: [{tags_str}]\n"
        f"sources:\n{sources_yaml}\n"
        f"---\n\n"
        f"# {note.note_title}\n\n"
        f"## Core Concept\n\n{note.core_concept}\n\n"
        f"## Subtopics\n\n{subtopics_md}\n\n"
        f"## Connections\n\n<!-- filled by Linker -->\n\n"
        f"## Sources\n\n{sources_list}\n"
    )


def run(synth_notes: list[SynthesizedNote], vault_path: str, inbox: str = "noter") -> list[str]:
    inbox_dir = Path(vault_path) / inbox
    inbox_dir.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    created = date.today().isoformat()
    paths = []

    for note in synth_notes:
        logger.debug("Writer: rendering note %r", note.note_title)
        tags = _infer_tags(note, client)
        name = _sanitize(note.note_title)
        path = _resolve_path(inbox_dir, name)
        if path.name != f"{name}.md":
            logger.debug("Writer: filename %r exists, using %r", f"{name}.md", path.name)
        content = _render_note(note, tags, created)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise WriterError(f"Failed to write '{note.note_title}' to {path}: {exc}") from exc
        logger.info("Writer: wrote %s", path)
        paths.append(str(path))

    return paths
