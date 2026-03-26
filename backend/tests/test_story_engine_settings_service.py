from __future__ import annotations

from uuid import uuid4

import pytest

from core.errors import AppError
from models.project import Project
from models.user import User
from services.story_engine_settings_service import (
    get_story_engine_guardian_consensus_config,
    _load_profile_config,
    _normalize_project_settings,
    build_story_engine_model_routing_project_summary,
    build_story_engine_settings_for_preset,
    build_story_engine_model_routing_payload,
    list_story_engine_model_preset_catalog,
    resolve_story_engine_model_routing,
)


def _build_project(*, story_engine_settings=None) -> Project:
    return Project(
        id=uuid4(),
        user_id=uuid4(),
        title="测试项目",
        genre="都市",
        tone="冷峻",
        story_engine_settings=story_engine_settings,
    )


def test_build_story_engine_model_routing_payload_uses_default_preset() -> None:
    payload = build_story_engine_model_routing_payload(_build_project())

    assert payload["active_preset_key"] == "balanced"
    assert payload["default_preset_key"] == "balanced"
    assert payload["effective_routing"]["guardian"]["model"] == "gpt-5.4"
    assert payload["effective_routing"]["logic_debunker"]["model"] == "claude-opus-4-6"


def test_normalize_project_settings_drops_same_as_preset_override() -> None:
    config = _load_profile_config()

    normalized = _normalize_project_settings(
        {
            "active_preset_key": "balanced",
            "manual_overrides": {
                "guardian": {"model": "gpt-5.4", "reasoning_effort": "high"},
                "commercial": {"model": "gpt-5.4", "reasoning_effort": "medium"},
            },
        },
        config=config,
        strict=True,
    )

    assert "guardian" not in normalized["manual_overrides"]
    assert normalized["manual_overrides"]["commercial"]["model"] == "gpt-5.4"


def test_normalize_project_settings_rejects_unknown_model() -> None:
    config = _load_profile_config()

    with pytest.raises(AppError) as exc_info:
        _normalize_project_settings(
            {
                "active_preset_key": "balanced",
                "manual_overrides": {
                    "guardian": {"model": "unknown-model", "reasoning_effort": "high"}
                },
            },
            config=config,
            strict=True,
        )

    assert exc_info.value.code == "story_engine.route_model_unknown"


def test_resolve_story_engine_model_routing_applies_project_override() -> None:
    routing = resolve_story_engine_model_routing(
        _build_project(
            story_engine_settings={
                "active_preset_key": "balanced",
                "manual_overrides": {
                    "stream_writer": {
                        "model": "deepseek-v3.2",
                        "reasoning_effort": "medium",
                    }
                },
            }
        )
    )

    assert routing["stream_writer"]["model"] == "deepseek-v3.2"
    assert routing["guardian"]["model"] == "gpt-5.4"


def test_build_story_engine_settings_for_preset_uses_default_when_missing() -> None:
    settings = build_story_engine_settings_for_preset()

    assert settings["active_preset_key"] == "balanced"
    assert settings["manual_overrides"] == {}


def test_list_story_engine_model_preset_catalog_exposes_default_and_presets() -> None:
    payload = list_story_engine_model_preset_catalog()

    assert payload["default_preset_key"] == "balanced"
    assert any(item["key"] == "momentum_hook" for item in payload["presets"])


def test_build_story_engine_model_routing_project_summary_reports_active_preset() -> None:
    project = _build_project(
        story_engine_settings={
            "active_preset_key": "momentum_hook",
            "manual_overrides": {
                "commercial": {
                    "model": "gpt-5.4",
                    "reasoning_effort": "medium",
                }
            },
        }
    )
    project.user = User(email="owner@example.com", password_hash="hashed-password")

    payload = build_story_engine_model_routing_project_summary(project)

    assert payload["title"] == "测试项目"
    assert payload["owner_email"] == "owner@example.com"
    assert payload["active_preset_key"] == "momentum_hook"
    assert payload["active_preset_label"] == "冲榜节奏"
    assert payload["manual_override_count"] == 1


def test_guardian_consensus_config_exposed_from_profile() -> None:
    payload = get_story_engine_guardian_consensus_config()

    assert payload["enabled"] is True
    assert payload["shadow_model"] == "gemini-3.1-pro-preview"
    assert payload["realtime_enabled"] is True
