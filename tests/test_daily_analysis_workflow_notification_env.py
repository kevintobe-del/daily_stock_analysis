# -*- coding: utf-8 -*-
"""Static checks for notification env mappings in 00-daily-analysis.yml."""

from pathlib import Path
import subprocess

import pytest
import yaml

from scripts.generate_notification_actions_env_table import (
    extract_managed_block,
    generate_table,
    normalize_markdown_block,
)
from src.services.notification_diagnostics import (
    P0_ACTIONS_ENV_KEYS,
    P3_ROUTE_ENV_KEYS,
    P4_NOISE_ACTIONS_ENV_KEYS,
    P6_CHANNEL_ACTIONS_ENV_KEYS,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT_DIR / ".github/workflows/00-daily-analysis.yml"
NOTIFICATIONS_DOC_PATH = ROOT_DIR / "docs/notifications.md"

P0_EXCLUDED_BEHAVIOR_SWITCHES = {
    "MERGE_EMAIL_NOTIFICATION",
}


def _load_daily_analysis_env() -> dict[str, str]:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["analyze"]["steps"]
    analyze_step = next((step for step in steps if step.get("name") == "执行股票分析"), None)
    available_step_names = [step.get("name", "<unnamed>") for step in steps]
    assert analyze_step is not None, (
        "Expected 00-daily-analysis.yml job analyze to include a step named "
        f"'执行股票分析'; available step names: {available_step_names}"
    )
    return analyze_step["env"]


def test_daily_analysis_maps_p0_notification_env_keys() -> None:
    env = _load_daily_analysis_env()

    for key in P0_ACTIONS_ENV_KEYS:
        assert key in env


def test_daily_analysis_maps_p3_notification_route_env_keys() -> None:
    env = _load_daily_analysis_env()

    for key in P3_ROUTE_ENV_KEYS:
        assert key in env


def test_daily_analysis_maps_p4_notification_noise_env_keys() -> None:
    env = _load_daily_analysis_env()

    for key in P4_NOISE_ACTIONS_ENV_KEYS:
        assert key in env


def test_daily_analysis_maps_p6_channel_env_keys() -> None:
    env = _load_daily_analysis_env()

    for key in P6_CHANNEL_ACTIONS_ENV_KEYS:
        assert key in env


def test_daily_analysis_feishu_status_accepts_webhook_or_app_bot_triad() -> None:
    status_line = next(
        line
        for line in WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
        if 'echo "  飞书:' in line
    )

    for key in ("FEISHU_WEBHOOK_URL", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_CHAT_ID"):
        assert key in status_line


def test_daily_analysis_keeps_deferred_behavior_switches_unmapped() -> None:
    env = _load_daily_analysis_env()

    for key in P0_EXCLUDED_BEHAVIOR_SWITCHES:
        assert key not in env


def test_daily_analysis_image_install_and_delivery_share_the_same_opt_in() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["analyze"]["steps"]
    install_step = next(step for step in steps if step.get("name") == "安装报告转图依赖")
    env = _load_daily_analysis_env()

    assert env["MARKDOWN_TO_IMAGE_CHANNELS"] == install_step["env"]["MARKDOWN_TO_IMAGE_CHANNELS"]
    assert "vars.MARKDOWN_TO_IMAGE_CHANNELS" in env["MARKDOWN_TO_IMAGE_CHANNELS"]
    assert "secrets.MARKDOWN_TO_IMAGE_CHANNELS" in env["MARKDOWN_TO_IMAGE_CHANNELS"]
    assert env["MD2IMG_ENGINE"] == "playwright"
    assert "MARKDOWN_TO_IMAGE_MAX_CHARS" in env
    assert steps.index(install_step) < next(
        index for index, step in enumerate(steps) if step.get("name") == "执行股票分析"
    )


def test_daily_analysis_installs_repository_local_chromium_and_cjk_fonts() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["analyze"]["steps"]
    install_step = next(step for step in steps if step.get("name") == "安装报告转图依赖")
    script = install_step["run"]

    assert "npm ci --prefix apps/dsa-web --ignore-scripts" in script
    assert "apps/dsa-web/node_modules/.bin/playwright install --with-deps chromium" in script
    assert "fonts-noto-cjk" in script
    assert "fonts-noto-color-emoji" in script


@pytest.mark.parametrize("channels", ["", " , , \t"])
def test_daily_analysis_skips_browser_install_when_images_are_disabled(channels: str) -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["analyze"]["steps"]
    install_step = next(step for step in steps if step.get("name") == "安装报告转图依赖")

    # No npm/sudo on PATH: the disabled branch must exit before installing anything.
    result = subprocess.run(
        ["/bin/bash", "-c", install_step["run"]],
        env={"MARKDOWN_TO_IMAGE_CHANNELS": channels, "PATH": "/nonexistent"},
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert "跳过浏览器安装" in result.stdout


def test_notification_actions_env_table_matches_generated_output() -> None:
    current = extract_managed_block(NOTIFICATIONS_DOC_PATH.read_text(encoding="utf-8"))
    expected = generate_table()

    assert normalize_markdown_block(current) == normalize_markdown_block(expected)
