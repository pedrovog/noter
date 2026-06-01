from typing import Literal

from pydantic import BaseModel


class NoteSpec(BaseModel):
    title: str
    subtopics: list[str]
    focus: str


class PlannerOutput(BaseModel):
    main_title: str
    generate_multiple_notes: bool
    notes: list[NoteSpec]
    search_queries: list[str]


class SourceResult(BaseModel):
    url: str
    title: str
    content: str
    source: Literal["auto", "user"]
    from_cache: bool = False


class SubtopicContent(BaseModel):
    title: str
    content: str


class SourceRef(BaseModel):
    url: str
    title: str


class SynthesizedNote(BaseModel):
    note_title: str
    core_concept: str
    subtopics: list[SubtopicContent]
    sources_used: list[SourceRef]
