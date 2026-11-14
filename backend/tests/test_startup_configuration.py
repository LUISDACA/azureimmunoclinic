"""Startup bootstrap configuration tests."""

from unittest.mock import AsyncMock

import pytest
from app import main


@pytest.mark.asyncio
async def test_startup_bootstrap_can_be_disabled_for_snapshot_validation(monkeypatch):
    seed_vaccines = AsyncMock()
    seed_admin_user = AsyncMock()
    monkeypatch.setattr(main.settings, "STARTUP_BOOTSTRAP_ENABLED", False)
    monkeypatch.setattr(main, "seed_vaccines", seed_vaccines)
    monkeypatch.setattr(main, "seed_admin_user", seed_admin_user)

    await main._run_startup_bootstrap(session=None)

    seed_vaccines.assert_not_awaited()
    seed_admin_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_bootstrap_preserves_existing_enabled_behavior(monkeypatch):
    seed_vaccines = AsyncMock()
    seed_admin_user = AsyncMock()
    monkeypatch.setattr(main.settings, "STARTUP_BOOTSTRAP_ENABLED", True)
    monkeypatch.setattr(main, "seed_vaccines", seed_vaccines)
    monkeypatch.setattr(main, "seed_admin_user", seed_admin_user)

    await main._run_startup_bootstrap(session=None)

    seed_vaccines.assert_awaited_once_with(None)
    seed_admin_user.assert_awaited_once_with(None)
