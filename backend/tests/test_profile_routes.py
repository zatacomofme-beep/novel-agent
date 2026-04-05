from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.v1.profile import (
    preference_detail,
    preference_patch,
    style_template_apply,
    style_template_clear_active,
)
from schemas.preferences import StyleTemplateApplyRequest, UserPreferenceUpdate


class _SingleReadUser:
    def __init__(self) -> None:
        self._id = uuid4()
        self.email = "writer@example.com"
        self._read_count = 0

    @property
    def id(self):  # type: ignore[override]
        self._read_count += 1
        if self._read_count > 1:
            raise RuntimeError("current_user.id accessed more than once")
        return self._id


class ProfileRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_preference_detail_snapshots_user_id_once(self) -> None:
        current_user = _SingleReadUser()
        session = SimpleNamespace()
        preference = SimpleNamespace()
        learning_snapshot = SimpleNamespace()
        expected = SimpleNamespace(ok=True)

        with patch(
            "api.v1.profile.get_or_create_user_preference",
            AsyncMock(return_value=preference),
        ) as mocked_get_or_create, patch(
            "api.v1.profile.get_preference_learning_snapshot",
            AsyncMock(return_value=learning_snapshot),
        ) as mocked_learning, patch(
            "api.v1.profile.to_user_preference_read",
            return_value=expected,
        ) as mocked_to_read:
            result = await preference_detail(current_user=current_user, session=session)

        self.assertIs(result, expected)
        mocked_get_or_create.assert_awaited_once_with(session, current_user._id)
        mocked_learning.assert_awaited_once_with(session, current_user._id)
        mocked_to_read.assert_called_once_with(preference, learning_snapshot)

    async def test_preference_patch_snapshots_user_id_once(self) -> None:
        current_user = _SingleReadUser()
        session = SimpleNamespace()
        payload = UserPreferenceUpdate(prose_style="sharp")
        preference = SimpleNamespace()
        updated = SimpleNamespace()
        learning_snapshot = SimpleNamespace()
        expected = SimpleNamespace(ok=True)

        with patch(
            "api.v1.profile.get_or_create_user_preference",
            AsyncMock(return_value=preference),
        ) as mocked_get_or_create, patch(
            "api.v1.profile.update_user_preference",
            AsyncMock(return_value=updated),
        ) as mocked_update, patch(
            "api.v1.profile.get_preference_learning_snapshot",
            AsyncMock(return_value=learning_snapshot),
        ) as mocked_learning, patch(
            "api.v1.profile.to_user_preference_read",
            return_value=expected,
        ):
            result = await preference_patch(
                payload=payload,
                current_user=current_user,
                session=session,
            )

        self.assertIs(result, expected)
        mocked_get_or_create.assert_awaited_once_with(session, current_user._id)
        mocked_update.assert_awaited_once_with(session, preference, payload)
        mocked_learning.assert_awaited_once_with(session, current_user._id)

    async def test_style_template_apply_snapshots_user_id_once(self) -> None:
        current_user = _SingleReadUser()
        session = SimpleNamespace()
        payload = StyleTemplateApplyRequest(mode="replace")
        preference = SimpleNamespace()
        updated = SimpleNamespace()
        learning_snapshot = SimpleNamespace()
        expected = SimpleNamespace(ok=True)

        with patch(
            "api.v1.profile.get_or_create_user_preference",
            AsyncMock(return_value=preference),
        ) as mocked_get_or_create, patch(
            "api.v1.profile.apply_style_template",
            AsyncMock(return_value=updated),
        ) as mocked_apply, patch(
            "api.v1.profile.get_preference_learning_snapshot",
            AsyncMock(return_value=learning_snapshot),
        ) as mocked_learning, patch(
            "api.v1.profile.to_user_preference_read",
            return_value=expected,
        ):
            result = await style_template_apply(
                template_key="dialogue_mystery",
                payload=payload,
                current_user=current_user,
                session=session,
            )

        self.assertIs(result, expected)
        mocked_get_or_create.assert_awaited_once_with(session, current_user._id)
        mocked_apply.assert_awaited_once_with(
            session,
            preference,
            "dialogue_mystery",
            mode="replace",
        )
        mocked_learning.assert_awaited_once_with(session, current_user._id)

    async def test_style_template_clear_active_snapshots_user_id_once(self) -> None:
        current_user = _SingleReadUser()
        session = SimpleNamespace()
        preference = SimpleNamespace()
        updated = SimpleNamespace()
        learning_snapshot = SimpleNamespace()
        expected = SimpleNamespace(ok=True)

        with patch(
            "api.v1.profile.get_or_create_user_preference",
            AsyncMock(return_value=preference),
        ) as mocked_get_or_create, patch(
            "api.v1.profile.clear_active_style_template",
            AsyncMock(return_value=updated),
        ) as mocked_clear, patch(
            "api.v1.profile.get_preference_learning_snapshot",
            AsyncMock(return_value=learning_snapshot),
        ) as mocked_learning, patch(
            "api.v1.profile.to_user_preference_read",
            return_value=expected,
        ):
            result = await style_template_clear_active(
                current_user=current_user,
                session=session,
            )

        self.assertIs(result, expected)
        mocked_get_or_create.assert_awaited_once_with(session, current_user._id)
        mocked_clear.assert_awaited_once_with(session, preference)
        mocked_learning.assert_awaited_once_with(session, current_user._id)


if __name__ == "__main__":
    unittest.main()
