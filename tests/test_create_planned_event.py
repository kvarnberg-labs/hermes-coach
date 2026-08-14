"""Tests for create_planned_event / delete_planned_event training tools.

Covers input validation, the FIT upload flow, and the FTP safety guard that
refuses to generate watt-based power targets when the athlete's FTP could not
be retrieved (the dangerous FTP=0 → 200% case).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import create_planned_event


@pytest.fixture
def mock_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fake HERMES_HOME with stored credentials for test-user-123."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    user_dir = hermes_home / "users" / "test-user-123"
    user_dir.mkdir(parents=True)
    (user_dir / "intervals_key").write_text("fake-api-key-abc")
    (user_dir / "intervals_athlete_id").write_text("i12345")


class TestValidation:
    def test_create_event_missing_name(self, mock_credentials):
        r = json.loads(create_planned_event.create_event(
            "test-user-123", date_iso="2026-08-20"))
        assert r["error"] == "name is required"

    def test_create_event_missing_date(self, mock_credentials):
        r = json.loads(create_planned_event.create_event(
            "test-user-123", name="Easy ride"))
        assert "date_iso is required" in r["error"]

    def test_create_event_invalid_date(self, mock_credentials):
        r = json.loads(create_planned_event.create_event(
            "test-user-123", name="X", date_iso="20-08-2026"))
        assert "Invalid date" in r["error"]

    def test_create_event_no_credentials(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        r = json.loads(create_planned_event.create_event(
            "ghost-user", name="X", date_iso="2026-08-20"))
        assert "error" in r  # no creds → friendly error


class TestCreateEventMinimal:
    def test_minimal_event_posts_payload(self, mock_credentials):
        with patch.object(create_planned_event, "_post_json") as mock_post:
            mock_post.return_value = {
                "id": 1, "name": "Easy", "type": "Ride",
                "start_date_local": "2026-08-20T09:00:00",
                "category": "WORKOUT",
            }
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Easy", date_iso="2026-08-20"))
        assert r["created"] is True
        assert r["event_id"] == 1
        payload = mock_post.call_args[0][3]
        assert payload["name"] == "Easy"
        assert payload["start_date_local"].startswith("2026-08-20T09:00")

    def test_duration_auto_computed_from_steps(self, mock_credentials):
        with patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190}, {"ftp": 250}]
            mock_post.return_value = {"id": 2, "name": "X", "type": "Ride"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="X", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "a", "duration_sec": 600},
                       {"name": "b", "duration_sec": 1200}]))
        payload = mock_post.call_args[0][3]
        # 600 + 1200 = 1800s = 30 min → moving_time seconds
        assert payload["moving_time"] == 1800


class TestFtpGuard:
    """The safety-critical guard: refuse watt-based targets when FTP is unknown."""

    def test_blocks_watt_targets_when_ftp_missing(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            # profile then sport-settings; FTP comes back 0 (fetch failed/missing)
            mock_req.side_effect = [{"max_hr": 190}, {"ftp": 0}]
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Threshold", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_min": 250, "power_max": 270}]))
        assert "error" in r
        assert "FTP" in r["error"]
        # Critical: no event was created → no dangerous workout shipped
        mock_post.assert_not_called()

    def test_blocks_watt_targets_when_ftp_fetch_raises(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            mock_req.side_effect = RuntimeError("boom")
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Threshold", date_iso="2026-08-20",
                event_type="VirtualRide",
                steps=[{"name": "on", "duration_sec": 600, "power_min": 250}]))
        assert "error" in r
        assert "FTP" in r["error"]
        mock_post.assert_not_called()

    def test_allows_pct_targets_when_ftp_missing(self, mock_credentials):
        """%FTP steps don't need the athlete's FTP — guard must not block them."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190}, {"ftp": 0}]
            mock_post.return_value = {"id": 999, "name": "Sweet", "type": "Ride"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Sweet", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_pct_min": 95, "power_pct_max": 100}]))
        assert r.get("created") is True
        assert r["event_id"] == 999

    def test_guard_skipped_for_run(self, mock_credentials):
        """Runs use pace, not FTP — guard must not trigger for Ride-only FTP logic."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190}, {"ftp": 0}]
            mock_post.return_value = {"id": 888, "name": "Tempo", "type": "Run"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Tempo", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "tempo", "duration_sec": 1200,
                        "pace_min": "5:00", "pace_max": "4:50"}]))
        assert r.get("created") is True

    def test_watts_converted_to_pct_when_ftp_known(self, mock_credentials):
        """Normal path: FTP available → watts passed to _build_fit_file as FTP."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT") as mock_fit:
            mock_req.side_effect = [{"max_hr": 190}, {"ftp": 250}]
            mock_post.return_value = {"id": 777, "name": "Sweet", "type": "Ride"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="Sweet", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_min": 200, "power_max": 220}]))
        # _build_fit_file(sport, steps, max_hr, ftp) — ftp is the 4th positional
        assert mock_fit.call_args[0][3] == 250


class TestDeleteEvent:
    def test_delete_event_success(self, mock_credentials):
        with patch.object(create_planned_event, "_delete_json", return_value=True):
            r = json.loads(create_planned_event.delete_event(
                "test-user-123", event_id=42))
        assert r == {"deleted": True, "event_id": 42}

    def test_delete_event_missing_id(self, mock_credentials):
        r = json.loads(create_planned_event.delete_event("test-user-123"))
        assert r["error"] == "event_id is required"


class TestPaceParse:
    def test_min_sec_per_km(self):
        # 5:00/km = 300s/km = 3.33 m/s
        assert create_planned_event._parse_pace_to_ms("5:00") == round(1000 / 300, 2)

    def test_numeric_passthrough(self):
        assert create_planned_event._parse_pace_to_ms(4.5) == 4.5

    def test_garbage_returns_zero(self):
        assert create_planned_event._parse_pace_to_ms("not a pace") == 0.0


class TestFitValidation:
    """The safety invariant now lives in the builder, not only the call site.

    These are pure (no fit_tool) — they verify the guard refuses unsafe inputs
    before any FIT encoding happens.
    """

    def test_rejects_watts_without_ftp(self):
        with pytest.raises(ValueError, match="FTP"):
            create_planned_event._validate_fit_targets(
                [{"power_min": 250, "power_max": 270}], max_hr=0, ftp=0)

    def test_rejects_hr_without_max_hr(self):
        with pytest.raises(ValueError, match="max_hr"):
            create_planned_event._validate_fit_targets(
                [{"hr_min": 150, "hr_max": 160}], max_hr=0, ftp=250)

    def test_allows_pct_power_without_ftp(self):
        create_planned_event._validate_fit_targets(
            [{"power_pct_min": 95, "power_pct_max": 100}], max_hr=0, ftp=0)

    def test_allows_small_watts_without_ftp(self):
        # values <= 20 are treated as % already, not dangerous
        create_planned_event._validate_fit_targets(
            [{"power_min": 10, "power_max": 15}], max_hr=0, ftp=0)

    def test_allows_pace_without_ftp_or_max_hr(self):
        create_planned_event._validate_fit_targets(
            [{"pace_min": "5:00", "pace_max": "4:50"}], max_hr=0, ftp=0)


class TestFitConversion:
    """Real FIT encoding tests — run only where fit_tool is installed
    (the runtime image). Skipped locally via importorskip.
    """

    def test_watts_converted_to_pct_ftp(self):
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "power_min": 200, "power_max": 220},
            max_hr=0, ftp=250)
        assert msg.custom_target_power_low == 80   # 200/250*100
        assert msg.custom_target_power_high == 88  # 220/250*100

    def test_pct_power_passthrough(self):
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "power_pct_min": 95, "power_pct_max": 100},
            max_hr=0, ftp=0)
        assert msg.custom_target_power_low == 95
        assert msg.custom_target_power_high == 100

    def test_hr_converted_to_pct_max_hr(self):
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "hr_min": 150, "hr_max": 160},
            max_hr=200, ftp=0)
        assert msg.custom_target_heart_rate_low == 75   # 150/200*100
        assert msg.custom_target_heart_rate_high == 80  # 160/200*100

    def test_pace_to_speed(self):
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "pace_min": "5:00", "pace_max": "4:50"},
            max_hr=0, ftp=0)
        assert msg.custom_target_speed_low == round(1000 / 300, 2)

    def test_name_truncated_to_16(self):
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 60, "name": "A very long step name here"},
            max_hr=0, ftp=0)
        assert len(msg.workout_step_name) == 16

    def test_build_fit_file_returns_bytes(self):
        pytest.importorskip("fit_tool")
        b = create_planned_event._build_fit_file(
            "Ride", [{"duration_sec": 600, "power_pct_min": 95, "power_pct_max": 100}],
            max_hr=190, ftp=250)
        assert isinstance(b, (bytes, bytearray)) and len(b) > 0
