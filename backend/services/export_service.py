from __future__ import annotations

import json
import re
from typing import Literal
from typing import Optional
from urllib.parse import quote

from fastapi.responses import PlainTextResponse

from services.chapter_gate_service import (
    apply_chapter_gate_metadata,
    apply_chapter_gate_metadata_many,
)


ExportFormat = Literal["txt", "md"]


def render_chapter_export(
    *,
    project_title: str,
    chapter,
    export_format: ExportFormat,
) -> str:
    apply_chapter_gate_metadata(chapter)
    if export_format == "md":
        return _render_chapter_markdown(project_title=project_title, chapter=chapter)
    return _render_chapter_text(project_title=project_title, chapter=chapter)


def render_project_export(
    *,
    project,
    export_format: ExportFormat,
) -> str:
    apply_chapter_gate_metadata_many(getattr(project, "chapters", []))
    if export_format == "md":
        return _render_project_markdown(project)
    return _render_project_text(project)


def build_export_response(
    *,
    content: str,
    filename: str,
) -> PlainTextResponse:
    disposition = (
        f'attachment; filename="{_ascii_filename(filename)}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": disposition},
    )


def build_project_export_filename(project_title: str, export_format: ExportFormat) -> str:
    return f"{_slug(project_title or 'project')}.{export_format}"


def build_chapter_export_filename(
    project_title: str,
    chapter,
    export_format: ExportFormat,
) -> str:
    title = chapter.title or f"chapter-{chapter.chapter_number}"
    filename_parts = [_slug(project_title or "project")]
    branch_key = _chapter_branch_key(chapter)
    volume_number = _chapter_volume_number(chapter)
    if branch_key:
        filename_parts.append(_slug(branch_key))
    if volume_number is not None:
        filename_parts.append(f"v{int(volume_number):02d}")
    filename_parts.extend(
        [
            f"chapter-{chapter.chapter_number:03d}",
            _slug(title),
        ]
    )
    return f"{'-'.join(filename_parts)}.{export_format}"


def _render_project_markdown(project) -> str:
    lines: list[str] = [
        f"# {project.title}",
        "",
        "## Metadata",
        f"- Status: {project.status}",
        f"- Genre: {project.genre or '未设置'}",
        f"- Theme: {project.theme or '未设置'}",
        f"- Tone: {project.tone or '未设置'}",
    ]
    lines.extend(_render_story_bible_markdown(project))

    chapters = sorted(project.chapters, key=lambda item: item.chapter_number)
    lines.extend(["", "## Chapters", ""])
    if not chapters:
        lines.append("_No chapters yet._")
        return "\n".join(lines).strip() + "\n"

    if not _project_has_structure(project):
        for chapter in chapters:
            lines.extend(
                [
                    f"### Chapter {chapter.chapter_number}: {chapter.title or f'第 {chapter.chapter_number} 章'}",
                    f"- Status: {chapter.status}",
                    f"- Word Count: {chapter.word_count or 0}",
                    *_render_chapter_gate_summary_markdown(chapter),
                    *_render_project_chapter_checkpoints_markdown(chapter),
                    "",
                    chapter.content or "_Empty chapter._",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    current_branch_key = None
    current_volume_key = None
    for chapter in _sorted_project_chapters(project):
        branch = _resolve_project_branch(project, chapter)
        volume = _resolve_project_volume(project, chapter)
        branch_group_key = _branch_group_key(branch)
        volume_group_key = _volume_group_key(volume)

        if branch_group_key != current_branch_key:
            current_branch_key = branch_group_key
            current_volume_key = None
            lines.extend(
                [
                    f"### Branch: {_branch_title(branch)}",
                    f"- Key: {_branch_key(branch)}",
                    f"- Status: {getattr(branch, 'status', 'active')}",
                ]
            )
            if getattr(branch, "description", None):
                lines.append(f"- Description: {branch.description}")
            lines.append("")

        if volume_group_key != current_volume_key:
            current_volume_key = volume_group_key
            lines.extend(
                [
                    f"#### Volume {_volume_number(volume)}: {_volume_title(volume)}",
                    f"- Status: {getattr(volume, 'status', 'planning')}",
                    "",
                ]
            )

        lines.extend(
            [
                f"##### Chapter {chapter.chapter_number}: {chapter.title or f'第 {chapter.chapter_number} 章'}",
                f"- Status: {chapter.status}",
                f"- Word Count: {chapter.word_count or 0}",
                *_render_chapter_gate_summary_markdown(chapter),
                *_render_project_chapter_checkpoints_markdown(chapter),
                "",
                chapter.content or "_Empty chapter._",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _render_project_text(project) -> str:
    lines: list[str] = [
        f"PROJECT: {project.title}",
        "",
        f"STATUS: {project.status}",
        f"GENRE: {project.genre or '未设置'}",
        f"THEME: {project.theme or '未设置'}",
        f"TONE: {project.tone or '未设置'}",
    ]
    lines.extend(_render_story_bible_text(project))

    chapters = sorted(project.chapters, key=lambda item: item.chapter_number)
    lines.extend(["", "CHAPTERS", "--------"])
    if not chapters:
        lines.append("No chapters yet.")
        return "\n".join(lines).strip() + "\n"

    if not _project_has_structure(project):
        for chapter in chapters:
            lines.extend(
                [
                    "",
                    f"CHAPTER {chapter.chapter_number}: {chapter.title or f'第 {chapter.chapter_number} 章'}",
                    f"STATUS: {chapter.status}",
                    f"WORD COUNT: {chapter.word_count or 0}",
                    *_render_chapter_gate_summary_text(chapter),
                    *_render_project_chapter_checkpoints_text(chapter),
                    "",
                    chapter.content or "(empty chapter)",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    current_branch_key = None
    current_volume_key = None
    for chapter in _sorted_project_chapters(project):
        branch = _resolve_project_branch(project, chapter)
        volume = _resolve_project_volume(project, chapter)
        branch_group_key = _branch_group_key(branch)
        volume_group_key = _volume_group_key(volume)

        if branch_group_key != current_branch_key:
            current_branch_key = branch_group_key
            current_volume_key = None
            lines.extend(
                [
                    "",
                    f"BRANCH: {_branch_title(branch)}",
                    f"BRANCH KEY: {_branch_key(branch)}",
                    f"BRANCH STATUS: {getattr(branch, 'status', 'active')}",
                ]
            )
            if getattr(branch, "description", None):
                lines.append(f"BRANCH DESCRIPTION: {branch.description}")

        if volume_group_key != current_volume_key:
            current_volume_key = volume_group_key
            lines.extend(
                [
                    "",
                    f"VOLUME {_volume_number(volume)}: {_volume_title(volume)}",
                    f"VOLUME STATUS: {getattr(volume, 'status', 'planning')}",
                ]
            )

        lines.extend(
            [
                "",
                f"CHAPTER {chapter.chapter_number}: {chapter.title or f'第 {chapter.chapter_number} 章'}",
                f"STATUS: {chapter.status}",
                f"WORD COUNT: {chapter.word_count or 0}",
                *_render_chapter_gate_summary_text(chapter),
                *_render_project_chapter_checkpoints_text(chapter),
                "",
                chapter.content or "(empty chapter)",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _render_chapter_markdown(*, project_title: str, chapter) -> str:
    lines: list[str] = [
        f"# {chapter.title or f'Chapter {chapter.chapter_number}'}",
        "",
        "## Metadata",
        f"- Project: {project_title}",
        f"- Chapter Number: {chapter.chapter_number}",
        f"- Status: {chapter.status}",
        f"- Word Count: {chapter.word_count or 0}",
    ]
    branch_title = _chapter_branch_title(chapter)
    branch_key = _chapter_branch_key(chapter)
    volume_title = _chapter_volume_title(chapter)
    volume_number = _chapter_volume_number(chapter)
    if branch_title is not None:
        lines.append(f"- Branch: {branch_title}")
    if branch_key is not None:
        lines.append(f"- Branch Key: {branch_key}")
    if volume_number is not None:
        lines.append(f"- Volume Number: {volume_number}")
    if volume_title is not None:
        lines.append(f"- Volume: {volume_title}")
    lines.extend(_render_chapter_gate_summary_markdown(chapter))
    if chapter.outline:
        lines.extend(
            [
                "",
                "## Outline",
                "```json",
                json.dumps(chapter.outline, ensure_ascii=False, indent=2),
                "```",
            ]
        )
    checkpoint_lines = _render_chapter_checkpoint_section_markdown(chapter)
    if checkpoint_lines:
        lines.extend(checkpoint_lines)
    lines.extend(
        [
            "",
            "## Content",
            "",
            chapter.content or "_Empty chapter._",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_chapter_text(*, project_title: str, chapter) -> str:
    lines: list[str] = [
        f"PROJECT: {project_title}",
        f"CHAPTER: {chapter.chapter_number}",
        f"TITLE: {chapter.title or f'第 {chapter.chapter_number} 章'}",
        f"STATUS: {chapter.status}",
        f"WORD COUNT: {chapter.word_count or 0}",
    ]
    branch_title = _chapter_branch_title(chapter)
    branch_key = _chapter_branch_key(chapter)
    volume_title = _chapter_volume_title(chapter)
    volume_number = _chapter_volume_number(chapter)
    if branch_title is not None:
        lines.append(f"BRANCH: {branch_title}")
    if branch_key is not None:
        lines.append(f"BRANCH KEY: {branch_key}")
    if volume_number is not None:
        lines.append(f"VOLUME NUMBER: {volume_number}")
    if volume_title is not None:
        lines.append(f"VOLUME: {volume_title}")
    lines.extend(_render_chapter_gate_summary_text(chapter))
    if chapter.outline:
        lines.extend(
            [
                "",
                "OUTLINE",
                "-------",
                json.dumps(chapter.outline, ensure_ascii=False, indent=2),
            ]
        )
    checkpoint_lines = _render_chapter_checkpoint_section_text(chapter)
    if checkpoint_lines:
        lines.extend(checkpoint_lines)
    lines.extend(
        [
            "",
            "CONTENT",
            "-------",
            chapter.content or "(empty chapter)",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_story_bible_markdown(project) -> list[str]:
    sections = [
        ("Characters", [item.name for item in project.characters]),
        ("World Settings", [item.title for item in project.world_settings]),
        ("Locations", [item.name for item in project.locations]),
        ("Plot Threads", [item.title for item in project.plot_threads]),
        ("Foreshadowing", [item.content for item in project.foreshadowing_items]),
        ("Timeline", [item.title for item in project.timeline_events]),
    ]

    lines: list[str] = ["", "## Story Bible"]
    for title, items in sections:
        lines.extend(["", f"### {title}"])
        if not items:
            lines.append("- None")
            continue
        lines.extend(f"- {item}" for item in items)
    return lines


def _render_story_bible_text(project) -> list[str]:
    sections = [
        ("CHARACTERS", [item.name for item in project.characters]),
        ("WORLD SETTINGS", [item.title for item in project.world_settings]),
        ("LOCATIONS", [item.name for item in project.locations]),
        ("PLOT THREADS", [item.title for item in project.plot_threads]),
        ("FORESHADOWING", [item.content for item in project.foreshadowing_items]),
        ("TIMELINE", [item.title for item in project.timeline_events]),
    ]

    lines: list[str] = ["", "STORY BIBLE", "-----------"]
    for title, items in sections:
        lines.extend(["", title])
        if not items:
            lines.append("- None")
            continue
        lines.extend(f"- {item}" for item in items)
    return lines


def _render_chapter_gate_summary_markdown(chapter) -> list[str]:
    lines = [
        f"- Final Gate: {_final_gate_label(getattr(chapter, 'final_gate_status', 'ready'))}",
        f"- Final Ready: {'Yes' if getattr(chapter, 'final_ready', True) else 'No'}",
        f"- Pending Checkpoints: {getattr(chapter, 'pending_checkpoint_count', 0)}",
        f"- Rejected Checkpoints: {getattr(chapter, 'rejected_checkpoint_count', 0)}",
    ]
    latest_title = getattr(chapter, "latest_checkpoint_title", None)
    latest_status = getattr(chapter, "latest_checkpoint_status", None)
    if latest_title:
        latest_label = latest_title
        if latest_status:
            latest_label = f"{latest_label} ({latest_status})"
        lines.append(f"- Latest Checkpoint: {latest_label}")
    latest_review_verdict = getattr(chapter, "latest_review_verdict", None)
    latest_review_summary = getattr(chapter, "latest_review_summary", None)
    if latest_review_verdict:
        lines.append(f"- Latest Review Verdict: {latest_review_verdict}")
    if latest_review_summary:
        lines.append(f"- Latest Review Summary: {latest_review_summary}")
    reason = getattr(chapter, "final_gate_reason", None)
    if reason:
        lines.append(f"- Gate Reason: {reason}")
    return lines


def _render_chapter_gate_summary_text(chapter) -> list[str]:
    lines = [
        f"FINAL GATE: {_final_gate_label(getattr(chapter, 'final_gate_status', 'ready'))}",
        f"FINAL READY: {'YES' if getattr(chapter, 'final_ready', True) else 'NO'}",
        f"PENDING CHECKPOINTS: {getattr(chapter, 'pending_checkpoint_count', 0)}",
        f"REJECTED CHECKPOINTS: {getattr(chapter, 'rejected_checkpoint_count', 0)}",
    ]
    latest_title = getattr(chapter, "latest_checkpoint_title", None)
    latest_status = getattr(chapter, "latest_checkpoint_status", None)
    if latest_title:
        latest_label = latest_title
        if latest_status:
            latest_label = f"{latest_label} ({latest_status})"
        lines.append(f"LATEST CHECKPOINT: {latest_label}")
    latest_review_verdict = getattr(chapter, "latest_review_verdict", None)
    latest_review_summary = getattr(chapter, "latest_review_summary", None)
    if latest_review_verdict:
        lines.append(f"LATEST REVIEW VERDICT: {latest_review_verdict}")
    if latest_review_summary:
        lines.append(f"LATEST REVIEW SUMMARY: {latest_review_summary}")
    reason = getattr(chapter, "final_gate_reason", None)
    if reason:
        lines.append(f"GATE REASON: {reason}")
    return lines


def _render_project_chapter_checkpoints_markdown(chapter) -> list[str]:
    checkpoints = list(getattr(chapter, "checkpoints", []) or [])
    if not checkpoints:
        return []
    lines = ["- Checkpoints:"]
    for checkpoint in checkpoints[:6]:
        lines.append(f"  - {_checkpoint_line_markdown(checkpoint)}")
    if len(checkpoints) > 6:
        lines.append(f"  - ... {len(checkpoints) - 6} more")
    return lines


def _render_project_chapter_checkpoints_text(chapter) -> list[str]:
    checkpoints = list(getattr(chapter, "checkpoints", []) or [])
    if not checkpoints:
        return []
    lines = ["CHECKPOINTS:"]
    for checkpoint in checkpoints[:6]:
        lines.append(f"- {_checkpoint_line_text(checkpoint)}")
    if len(checkpoints) > 6:
        lines.append(f"- ... {len(checkpoints) - 6} more")
    return lines


def _render_chapter_checkpoint_section_markdown(chapter) -> list[str]:
    checkpoints = list(getattr(chapter, "checkpoints", []) or [])
    if not checkpoints:
        return []
    lines = ["", "## Checkpoints"]
    for checkpoint in checkpoints:
        lines.append(f"- {_checkpoint_line_markdown(checkpoint)}")
    return lines


def _render_chapter_checkpoint_section_text(chapter) -> list[str]:
    checkpoints = list(getattr(chapter, "checkpoints", []) or [])
    if not checkpoints:
        return []
    lines = ["", "CHECKPOINTS", "-----------"]
    for checkpoint in checkpoints:
        lines.append(f"- {_checkpoint_line_text(checkpoint)}")
    return lines


def _checkpoint_line_markdown(checkpoint) -> str:
    parts = [
        f"[{getattr(checkpoint, 'status', 'unknown')}]",
        getattr(checkpoint, "title", None) or "Untitled checkpoint",
    ]
    checkpoint_type = getattr(checkpoint, "checkpoint_type", None)
    if checkpoint_type:
        parts.append(f"· {checkpoint_type}")
    decision_note = getattr(checkpoint, "decision_note", None)
    if decision_note:
        parts.append(f"· Note: {decision_note}")
    return " ".join(parts)


def _checkpoint_line_text(checkpoint) -> str:
    parts = [
        f"[{getattr(checkpoint, 'status', 'unknown')}]",
        getattr(checkpoint, "title", None) or "Untitled checkpoint",
    ]
    checkpoint_type = getattr(checkpoint, "checkpoint_type", None)
    if checkpoint_type:
        parts.append(f"TYPE={checkpoint_type}")
    decision_note = getattr(checkpoint, "decision_note", None)
    if decision_note:
        parts.append(f"NOTE={decision_note}")
    return " | ".join(parts)


def _final_gate_label(status: str) -> str:
    if status == "blocked_pending":
        return "blocked_pending"
    if status == "blocked_rejected":
        return "blocked_rejected"
    if status == "blocked_review":
        return "blocked_review"
    return "ready"


def _slug(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9\-_]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or "export"


def _ascii_filename(filename: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9._-]+', "-", filename).strip("-")
    return safe or "export.txt"


def _project_has_structure(project) -> bool:
    if getattr(project, "branches", None) or getattr(project, "volumes", None):
        return True
    return any(
        getattr(chapter, "branch", None) is not None
        or getattr(chapter, "volume", None) is not None
        or getattr(chapter, "branch_id", None) is not None
        or getattr(chapter, "volume_id", None) is not None
        for chapter in getattr(project, "chapters", [])
    )


def _sorted_project_chapters(project) -> list:
    return sorted(
        project.chapters,
        key=lambda chapter: (
            0 if _resolve_project_branch(project, chapter) and getattr(_resolve_project_branch(project, chapter), "is_default", False) else 1,
            _branch_key(_resolve_project_branch(project, chapter)),
            _volume_number(_resolve_project_volume(project, chapter)),
            chapter.chapter_number,
        ),
    )


def _resolve_project_branch(project, chapter):
    branch = getattr(chapter, "branch", None)
    if branch is not None:
        return branch

    branch_id = getattr(chapter, "branch_id", None)
    for candidate in getattr(project, "branches", []) or []:
        if getattr(candidate, "id", None) == branch_id:
            return candidate

    branches = getattr(project, "branches", []) or []
    default_branch = next((item for item in branches if getattr(item, "is_default", False)), None)
    if default_branch is not None:
        return default_branch
    if branches:
        return branches[0]
    return None


def _resolve_project_volume(project, chapter):
    volume = getattr(chapter, "volume", None)
    if volume is not None:
        return volume

    volume_id = getattr(chapter, "volume_id", None)
    for candidate in getattr(project, "volumes", []) or []:
        if getattr(candidate, "id", None) == volume_id:
            return candidate

    volumes = getattr(project, "volumes", []) or []
    if volumes:
        return sorted(volumes, key=lambda item: getattr(item, "volume_number", 1))[0]
    return None


def _branch_group_key(branch) -> str:
    return f"{_branch_key(branch)}::{_branch_title(branch)}"


def _volume_group_key(volume) -> str:
    return f"{_volume_number(volume)}::{_volume_title(volume)}"


def _branch_title(branch) -> str:
    return getattr(branch, "title", None) or "主线"


def _branch_key(branch) -> str:
    return getattr(branch, "key", None) or "main"


def _volume_title(volume) -> str:
    return getattr(volume, "title", None) or "第一卷"


def _volume_number(volume) -> int:
    return int(getattr(volume, "volume_number", 1) or 1)


def _chapter_branch_title(chapter) -> Optional[str]:
    branch = getattr(chapter, "branch", None)
    if branch is not None:
        return getattr(branch, "title", None)
    return getattr(chapter, "branch_title", None)


def _chapter_branch_key(chapter) -> Optional[str]:
    branch = getattr(chapter, "branch", None)
    if branch is not None:
        return getattr(branch, "key", None)
    return getattr(chapter, "branch_key", None)


def _chapter_volume_title(chapter) -> Optional[str]:
    volume = getattr(chapter, "volume", None)
    if volume is not None:
        return getattr(volume, "title", None)
    return getattr(chapter, "volume_title", None)


def _chapter_volume_number(chapter) -> Optional[int]:
    volume = getattr(chapter, "volume", None)
    if volume is not None:
        number = getattr(volume, "volume_number", None)
        return int(number) if number is not None else None
    number = getattr(chapter, "volume_number", None)
    return int(number) if number is not None else None
