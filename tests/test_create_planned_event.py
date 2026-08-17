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
            mock_req.side_effect = [{"max_hr": 190, "ftp": 250}]
            mock_post.return_value = {"id": 2, "name": "X", "type": "Ride"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="X", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "a", "duration_sec": 600},
                       {"name": "b", "duration_sec": 1200}]))
        payload = mock_post.call_args[0][3]
        # 600 + 1200 = 1800s = 30 min → moving_time seconds
        assert payload["moving_time"] == 1800


class TestEmptyStepsGuard:
    """A non-empty steps list with no real content (e.g. [{}] when the model
    couldn't fill the step schema) must be refused — not turned into a
    degenerate FIT that intervals.icu accepts with a broken workout. This was
    the create→delete loop root cause: the model sent [{}], the tool built a
    0-duration/no-target FIT, reported has_steps=True, and the model kept
    deleting and retrying."""

    def test_rejects_single_empty_step(self, mock_credentials):
        with patch.object(create_planned_event, "_post_json") as mock_post:
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Run", date_iso="2026-08-20",
                event_type="Run", steps=[{}]))
        assert "error" in r
        assert "empty" in r["error"]
        mock_post.assert_not_called()

    def test_rejects_multiple_empty_steps(self, mock_credentials):
        with patch.object(create_planned_event, "_post_json") as mock_post:
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Run", date_iso="2026-08-20",
                event_type="Run", steps=[{}, {}]))
        assert "error" in r
        assert "empty" in r["error"]
        mock_post.assert_not_called()

    def test_allows_step_with_duration(self, mock_credentials):
        """A step with duration but no target is not 'empty' — a real step
        (e.g. a free-ride block). The guard must not block it."""
        with patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 1, "name": "Run", "type": "Run"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Run", date_iso="2026-08-20",
                event_type="Run", steps=[{"name": "easy", "duration_sec": 600}]))
        assert r.get("created") is True

    def test_rejects_bare_target_string_without_duration(self, mock_credentials):
        """A step with only a target string (no duration, no bounds) is empty —
        it would build a 0-duration/0-target step. The old guard counted a
        `target` string as content and let it through."""
        with patch.object(create_planned_event, "_post_json") as mock_post:
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Run", date_iso="2026-08-20",
                event_type="Run", steps=[{"target": "PACE"}]))
        assert "error" in r
        assert "empty" in r["error"]
        mock_post.assert_not_called()

    def test_rejects_empty_step_mixed_with_good_step(self, mock_credentials):
        """A single junk step among valid ones must reject the whole request —
        the old list-wide any() let a trailing {} ride along and become a
        0-duration step in the FIT."""
        with patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_request") as mock_req:
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Run", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "easy", "duration_sec": 600, "pace_min": "5:00"},
                       {}]))
        assert "error" in r
        assert "empty" in r["error"]
        # names the offending index so the model can fix just that step
        assert "1" in r["error"]
        mock_post.assert_not_called()


class TestStepSchema:
    def test_steps_items_define_properties(self):
        """The step item schema must enumerate fields — a bare {type: object}
        leaves the model with no fields to fill, so strict tool-call enforcement
        emits empty {} steps (the create→delete loop root cause)."""
        registered = {}

        class FakeCtx:
            def register_tool(self, name, toolset, schema, handler):
                registered[name] = schema

        create_planned_event.register_tools(FakeCtx())
        steps = registered["create_planned_event"]["parameters"]["properties"]["steps"]
        assert steps["type"] == "array"
        props = steps["items"].get("properties", {})
        for f in ("duration_sec", "name", "type", "pace_min", "pace_max",
                  "hr_min", "hr_max", "power_min", "power_max",
                  "power_pct_min", "power_pct_max"):
            assert f in props, f"step schema missing field {f}"


class TestSportMapping:
    """FIT sport and event target come from one shared map, so a run can never
    be written into the FIT as a ride (the old sport_map covered only Run +
    the cycling family; TrailRun/VirtualRun fell through to CYCLING)."""

    def test_run_variants_map_to_running_and_pace(self):
        for et in ("Run", "TrailRun", "VirtualRun"):
            assert create_planned_event._SPORT_META[et] == ("RUNNING", "PACE")

    def test_ride_variants_map_to_cycling_and_power(self):
        for et in ("Ride", "VirtualRide", "GravelRide", "MountainBikeRide"):
            assert create_planned_event._SPORT_META[et] == ("CYCLING", "POWER")

    def test_swim_walk_have_correct_sport_no_default_target(self):
        assert create_planned_event._SPORT_META["Swim"] == ("SWIMMING", None)
        assert create_planned_event._SPORT_META["Walk"] == ("WALKING", None)

    def test_unknown_sport_has_no_default_target(self):
        assert create_planned_event._sport_target("Yoga") is None

    def test_event_target_set_for_trailrun(self, mock_credentials):
        """Regression: TrailRun must get event-level PACE target (it used to be
        recognized for the target but mislabeled CYCLING in the FIT)."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 1, "name": "Trail", "type": "TrailRun"}
            create_planned_event.create_event(
                "test-user-123", name="Trail", date_iso="2026-08-20",
                event_type="TrailRun",
                steps=[{"name": "climb", "duration_sec": 600, "pace_min": "6:00"}])
        payload = mock_post.call_args[0][3]
        assert payload["target"] == "PACE"

    def test_trailrun_fit_sport_is_running(self):
        """The FIT Sport enum resolved for TrailRun must be RUNNING, not the
        old CYCLING default."""
        pytest.importorskip("fit_tool")
        from fit_tool.profile.profile_type import Sport
        b = create_planned_event._build_fit_file(
            "TrailRun",
            [{"duration_sec": 600, "pace_min": "6:00", "pace_max": "5:30"}],
            max_hr=0, ftp=0)
        assert isinstance(b, (bytes, bytearray)) and len(b) > 0
        # Resolve the same way the builder does and confirm it's RUNNING.
        assert getattr(Sport, create_planned_event._SPORT_META["TrailRun"][0]) == Sport.RUNNING

    def test_variant_event_uses_canonical_settings_sport(self, mock_credentials):
        """TrailRun shares Run's FTP/max_hr — fetch sport-settings for the
        canonical base sport (Run), not the variant (TrailRun), which can 404
        (the athlete configures 'Run', not 'TrailRun')."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 1, "name": "Trail", "type": "TrailRun"}
            create_planned_event.create_event(
                "test-user-123", name="Trail", date_iso="2026-08-20",
                event_type="TrailRun",
                steps=[{"name": "climb", "duration_sec": 600, "pace_min": "6:00"}])
        assert mock_req.call_args[0][2] == "/athlete/i12345/sport-settings/Run"


class TestTargetPrecedence:
    """When a step supplies more than one metric, the sport's primary target
    wins so the step matches the event target (old code was always HR-first,
    discarding the sport's own metric)."""

    def test_run_prefers_pace_over_hr(self):
        pytest.importorskip("fit_tool")
        from fit_tool.profile.profile_type import WorkoutStepTarget
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "hr_min": 150, "hr_max": 160,
             "pace_min": "5:00", "pace_max": "4:50"},
            max_hr=200, ftp=0, primary="PACE")
        assert msg.target_type == WorkoutStepTarget.SPEED.value
        assert msg.custom_target_speed_low == round(1000 / 300, 2)

    def test_ride_prefers_power_over_hr(self):
        pytest.importorskip("fit_tool")
        from fit_tool.profile.profile_type import WorkoutStepTarget
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "hr_min": 150, "hr_max": 160,
             "power_pct_min": 90, "power_pct_max": 95},
            max_hr=200, ftp=0, primary="POWER")
        assert msg.target_type == WorkoutStepTarget.POWER.value
        assert msg.custom_target_power_low == 90

    def test_falls_back_to_hr_when_no_primary(self):
        pytest.importorskip("fit_tool")
        from fit_tool.profile.profile_type import WorkoutStepTarget
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "hr_min": 150, "hr_max": 160,
             "pace_min": "5:00", "pace_max": "4:50"},
            max_hr=200, ftp=0)
        assert msg.target_type == WorkoutStepTarget.HEART_RATE.value
        assert msg.custom_target_heart_rate_low == 75  # 150/200*100


class TestFtpGuard:
    """The safety-critical guard: refuse watt-based targets when FTP is unknown."""

    def test_blocks_watt_targets_when_ftp_missing(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            # sport-settings; FTP comes back 0 (fetch failed/missing)
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
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
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 999, "name": "Sweet", "type": "Ride"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Sweet", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_pct_min": 95, "power_pct_max": 100}]))
        assert r.get("created") is True
        assert r["event_id"] == 999

    def test_ftp_guard_skipped_for_pace_step(self, mock_credentials):
        """The FTP guard is sport-agnostic (not Ride-only): it only triggers on
        watt targets. A pace step has no watts, so it must not be blocked even
        with ftp=0."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
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
            mock_req.side_effect = [{"max_hr": 190, "ftp": 250}]
            mock_post.return_value = {"id": 777, "name": "Sweet", "type": "Ride"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="Sweet", date_iso="2026-08-20",
                event_type="Ride",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_min": 200, "power_max": 220}]))
        # _build_fit_file(sport, steps, max_hr, ftp) — ftp is the 4th positional
        assert mock_fit.call_args[0][3] == 250
        # B1 regression guard: ftp/max_hr come from sport-settings, not the
        # profile endpoint (which never returns max_hr).
        assert mock_req.call_args[0][2] == "/athlete/i12345/sport-settings/Ride"

    def test_blocks_watt_targets_on_non_cycling_sport(self, mock_credentials):
        """The FTP guard is sport-agnostic (de-scoped from Ride-only): watt
        targets are dangerous for any sport, so a Run with watts + unknown FTP
        must be refused just like a Ride."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="X", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "on", "duration_sec": 600,
                        "power_min": 250, "power_max": 270}]))
        assert "error" in r
        assert "FTP" in r["error"]
        mock_post.assert_not_called()


class TestHrGuard:
    """Mirror of the FTP guard: refuse BPM targets when max_hr is unknown,
    rather than converting against a guessed default (was 193)."""

    def test_blocks_hr_targets_when_max_hr_missing(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            # sport-settings returns no max_hr (ftp known)
            mock_req.side_effect = [{"ftp": 250}]
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Z2", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "z2", "duration_sec": 1800,
                        "hr_min": 130, "hr_max": 145}]))
        assert "error" in r
        assert "max_hr" in r["error"]
        mock_post.assert_not_called()

    def test_blocks_hr_targets_when_settings_fetch_raises(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            mock_req.side_effect = RuntimeError("boom")
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Z2", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "z2", "duration_sec": 1800, "hr_min": 130}]))
        assert "error" in r
        assert "max_hr" in r["error"]
        mock_post.assert_not_called()

    def test_allows_hr_targets_when_max_hr_known(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT"):
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 5, "name": "Z2", "type": "Run"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Z2", date_iso="2026-08-20",
                event_type="Run",
                steps=[{"name": "z2", "duration_sec": 1800,
                        "hr_min": 130, "hr_max": 145}]))
        assert r.get("created") is True


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

    def test_rejects_any_watts_without_ftp(self):
        # any watt value with no FTP would be read as %FTP by Garmin — refuse,
        # regardless of magnitude (no <=20 guess; use power_pct_* for %)
        with pytest.raises(ValueError, match="FTP"):
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

    def test_create_event_attaches_fit_to_payload(self, mock_credentials):
        pytest.importorskip("fit_tool")
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post:
            mock_req.side_effect = [{"max_hr": 190, "ftp": 0}]
            mock_post.return_value = {"id": 1, "name": "Run", "type": "Run",
                                      "start_date_local": "2026-08-20T09:00:00",
                                      "category": "WORKOUT"}
            r = json.loads(create_planned_event.create_event(
                "test-user-123", name="Tempo", date_iso="2026-08-20", event_type="Run",
                steps=[{"name": "on", "duration_sec": 600,
                        "pace_min": "5:00", "pace_max": "5:30"}]))
        assert r["created"] is True
        payload = mock_post.call_args[0][3]
        assert payload["filename"] == "workout.fit"
        assert payload["file_contents_base64"]  # non-empty base64 FIT attached

    def test_step_description_mapped_to_notes(self):
        """The schema's optional `description` field must reach the FIT (not be
        silently ignored — the same anti-pattern as the empty-steps bug)."""
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "pace_min": "5:00", "description": "stay relaxed"},
            max_hr=0, ftp=0)
        assert msg.notes == "stay relaxed"
        # absent/blank description must not set notes
        msg2 = create_planned_event._step_message(
            {"duration_sec": 600, "pace_min": "5:00"}, max_hr=0, ftp=0)
        assert not msg2.notes

    def test_step_description_truncated(self):
        """Long descriptions are capped so they can't bloat the FIT or trip a
        downstream limit (notes has no FIT spec max, unlike workout_step_name)."""
        pytest.importorskip("fit_tool")
        msg = create_planned_event._step_message(
            {"duration_sec": 600, "pace_min": "5:00", "description": "x" * 400},
            max_hr=0, ftp=0)
        assert len(msg.notes) == 255


class TestIndoorFtp:
    """Indoor events (indoor=True, e.g. Zwift/VirtualRide) use indoor_ftp from
    sport-settings for the watts->%FTP conversion, falling back to outdoor ftp."""

    def test_indoor_event_uses_indoor_ftp(self, mock_credentials):
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT") as mock_fit:
            mock_req.side_effect = [{"max_hr": 190, "ftp": 250, "indoor_ftp": 220}]
            mock_post.return_value = {"id": 1, "name": "Zwift", "type": "VirtualRide"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="Zwift", date_iso="2026-08-20",
                event_type="VirtualRide", indoor=True,
                steps=[{"name": "on", "duration_sec": 600, "power_min": 200, "power_max": 220}]))
        # _build_fit_file(sport, steps, max_hr, ftp) — ftp is the 4th positional
        assert mock_fit.call_args[0][3] == 220  # indoor_ftp, not outdoor 250

    def test_indoor_event_falls_back_to_outdoor_ftp(self, mock_credentials):
        """If indoor_ftp isn't set, fall back to outdoor ftp for indoor events."""
        with patch.object(create_planned_event, "_request") as mock_req, \
             patch.object(create_planned_event, "_post_json") as mock_post, \
             patch.object(create_planned_event, "_build_fit_file", return_value=b"FIT") as mock_fit:
            mock_req.side_effect = [{"max_hr": 190, "ftp": 250}]  # no indoor_ftp
            mock_post.return_value = {"id": 1, "name": "Zwift", "type": "VirtualRide"}
            json.loads(create_planned_event.create_event(
                "test-user-123", name="Zwift", date_iso="2026-08-20",
                event_type="VirtualRide", indoor=True,
                steps=[{"name": "on", "duration_sec": 600, "power_min": 200, "power_max": 220}]))
        assert mock_fit.call_args[0][3] == 250  # falls back to outdoor
