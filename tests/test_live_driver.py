"""`scripts/live_driver.py`: the replay loop, offline.

No network and no key: `urllib.request.urlopen` is replaced by a scripted fake,
so these tests grade the driver's protocol handling, not a model. A real model
call happens only when the operator sets HERMES_DRIVER_API_KEY.

The last test here runs against the committed case data (fixture names, shapes)
with no model involved: it is what keeps the driver's fixture table honest.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import decision_predicates as dp  # noqa: E402
import eval_decisions  # noqa: E402
import live_driver  # noqa: E402

DECISIONS = ROOT / "tests" / "golden" / "decisions"
CASES = [yaml.safe_load(p.read_text(encoding="utf-8"))
         for p in sorted(DECISIONS.glob("*.yaml"))]
# The committed case count the driver must be able to replay. A silent drop to
# zero cases would make the fixture-table test below vacuous, not red.
MIN_CASES = 12
KEY = "sk-test-0123456789-not-a-real-key"


class FakeResponse:
    """Just enough of the urlopen response for `_post`: a body in a context."""

    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> bool:
        return False


def fake_model(monkeypatch, replies: list[dict]) -> list[dict]:
    """Script the model: each request consumes the next reply, the last repeats.

    Returns the request bodies the driver sent, so a test can check the tools and
    the temperature that went out rather than only what came back.
    """
    sent: list[dict] = []

    def urlopen(request, timeout=None):
        sent.append(json.loads(request.data))
        message = replies.pop(0) if len(replies) > 1 else replies[0]
        return FakeResponse({"choices": [{"message": message}]})

    monkeypatch.setattr(live_driver.urllib.request, "urlopen", urlopen)
    return sent


def tool_call(name: str, args: dict | None = None, call_id: str = "call_1") -> dict:
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args or {})}}


def case(**overrides) -> dict:
    """A case as eval_decisions.py ships it: parsed fixture payloads in _fixtures."""
    base = {
        "id": "dm-load-question-live",
        "chat_type": "dm",
        "athlete_message": "How's my training load looking?",
        "fixtures": ["athlete-profile-2026-09-16.json", "wellness-2026-11-10.json"],
        "_fixtures": {
            "athlete-profile-2026-09-16.json": {"id": "i000000", "ftp": 280},
            "wellness-2026-11-10.json": {"id": "2026-11-10", "hrv": 60},
        },
    }
    base.update(overrides)
    return base


def run(monkeypatch, capsys, payload: dict) -> tuple[int, str, dict]:
    """Drive one case through main() and parse what it printed."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = live_driver.main()
    out = capsys.readouterr().out
    return code, out, (json.loads(out) if out.strip() else {})


@pytest.fixture(autouse=True)
def _driver_env(monkeypatch):
    """Only the key: an ambient base URL or max steps must not reach these tests."""
    monkeypatch.setenv("HERMES_DRIVER_API_KEY", KEY)
    for name in ("HERMES_DRIVER_BASE_URL", "HERMES_DRIVER_MODEL", "HERMES_DRIVER_MAX_STEPS"):
        monkeypatch.delenv(name, raising=False)


def test_missing_key_exits_3_and_prints_no_key(monkeypatch, capsys):
    monkeypatch.delenv("HERMES_DRIVER_API_KEY")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(case())))
    with pytest.raises(SystemExit) as excinfo:
        live_driver.main()
    assert excinfo.value.code == 3
    out, err = capsys.readouterr()
    assert "set HERMES_DRIVER_API_KEY" in err
    assert out == ""
    assert KEY not in err


def test_tool_call_is_replayed_from_the_fixture_then_answered(monkeypatch, capsys):
    sent = fake_model(monkeypatch, [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("get_wellness", {"oldest": "2026-11-10"})]},
        {"role": "assistant", "content": "Load is steady: HRV 60."},
    ])
    code, _out, transcript = run(monkeypatch, capsys, case())

    assert code == 0
    assert transcript["chat_type"] == "dm"          # copied from the case
    assert transcript["case_id"] == "dm-load-question-live"
    user, tool, assistant = transcript["messages"]
    assert (user["role"], user["content"]) == ("user", "How's my training load looking?")
    assert tool["role"] == "tool" and tool["tool"] == "get_wellness"
    assert tool["ok"] is True
    assert tool["args"] == {"oldest": "2026-11-10"}
    assert json.loads(tool["content"]) == {"id": "2026-11-10", "hrv": 60}
    assert assistant["role"] == "assistant" and "steady" in assistant["content"]
    assert transcript.get("truncated") is None

    # Real schemas on the wire, not invented ones: the fixture producers are
    # among the tools the plugin registers, and the request is greedy-free.
    names = [spec["function"]["name"] for spec in sent[0]["tools"]]
    assert {"get_wellness", "get_athlete_profile", "verify_athlete_identity"} <= set(names)
    assert len(names) >= 20
    assert sent[0]["temperature"] == 0
    assert sent[0]["model"] == live_driver.DEFAULT_MODEL
    assert sent[0]["messages"][0]["role"] == "system"


def test_tool_without_a_fixture_reports_it_and_the_loop_continues(monkeypatch, capsys):
    fake_model(monkeypatch, [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("terminal", {"command": "ls"})]},
        {"role": "assistant", "content": "I cannot do that in a DM."},
    ])
    code, _out, transcript = run(monkeypatch, capsys, case())

    assert code == 0
    tool = transcript["messages"][1]
    assert tool["tool"] == "terminal"
    assert tool["ok"] is False
    assert json.loads(tool["content"]) == {"error": "no fixture for terminal in this case"}
    assert transcript["messages"][-1]["role"] == "assistant"
    assert transcript.get("truncated") is None


def test_max_steps_truncates_and_still_emits_a_transcript(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_DRIVER_MAX_STEPS", "2")
    fake_model(monkeypatch, [{"role": "assistant", "content": None,
                              "tool_calls": [tool_call("get_wellness")]}])
    code, _out, transcript = run(monkeypatch, capsys, case())

    assert code == 0
    assert transcript["truncated"] is True
    assert [m["tool"] for m in transcript["messages"] if m["role"] == "tool"] == [
        "get_wellness", "get_wellness"]
    assert not [m for m in transcript["messages"] if m["role"] == "assistant"]


def test_unknown_fixture_prefix_exits_naming_the_file(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(case(
        fixtures=["mystery-2026-11-10.json"],
        _fixtures={"mystery-2026-11-10.json": {"ids": []}}))))
    with pytest.raises(SystemExit) as excinfo:
        live_driver.main()
    assert excinfo.value.code != 0
    assert "mystery-2026-11-10.json" in str(excinfo.value)


def test_case_with_no_fixtures_is_refused(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        case(fixtures=[], _fixtures={}))))
    with pytest.raises(SystemExit) as excinfo:
        live_driver.main()
    assert excinfo.value.code != 0
    assert "no fixture payloads" in str(excinfo.value)
    assert capsys.readouterr().out == ""


def test_api_key_never_reaches_stdout(monkeypatch, capsys):
    fake_model(monkeypatch, [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("get_wellness", {"discord_id": "1234567890"})]},
        {"role": "assistant", "content": "Done."},
    ])
    _code, out, transcript = run(monkeypatch, capsys, case())

    assert KEY not in out
    assert "1234567890" not in out          # discord_id is dropped from echoed args
    assert transcript["messages"][1]["args"] == {}


def test_transcript_from_the_runner_payload_scores_under_the_real_gate(monkeypatch, capsys):
    """The exact stdin eval_decisions.drive_live builds, scored by the real gate.

    Shape valid JSON is not enough: the driver's messages must be what
    decision_predicates reads.
    """
    committed = next(c for c in eval_decisions.load_cases(DECISIONS)
                     if c["id"] == "dm-load-question-2026-11-10")
    payload = {**committed, "_fixtures": eval_decisions.load_fixtures(committed, DECISIONS)}
    fake_model(monkeypatch, [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("verify_athlete_identity", call_id="a")]},
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("get_wellness", call_id="b")]},
        {"role": "assistant", "content": "Load is steady."},
    ])
    _code, _out, transcript = run(monkeypatch, capsys, payload)

    assert transcript["chat_type"] == committed["chat_type"]
    gated = dp.evaluate(committed, transcript)["gated"]
    assert [row["predicate"] for row in gated] == ["identity_before_data"]
    assert gated[0]["passed"], gated[0]["reason"]


def test_http_error_exits_with_status_and_body(monkeypatch, capsys):
    """A failed model call must not print the request headers (they carry the key)."""

    def urlopen(request, timeout=None):
        raise live_driver.urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"invalid api key"}}'))

    monkeypatch.setattr(live_driver.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(case())))
    with pytest.raises(SystemExit) as excinfo:
        live_driver.main()
    assert excinfo.value.code != 0
    message = str(excinfo.value)
    assert "401" in message and "invalid api key" in message
    assert KEY not in message


# --- the committed cases --------------------------------------------------

def test_committed_case_corpus_is_present():
    """A base branch without the cases would make the test below collect nothing."""
    assert len(CASES) >= MIN_CASES, (
        f"found {len(CASES)} cases in {DECISIONS}, expected at least {MIN_CASES}: "
        "the decision eval lives on feat/decision-eval, so this driver must stack on it")


@pytest.mark.parametrize("committed", CASES, ids=[c["id"] for c in CASES])
def test_committed_case_fixtures_map_to_tools(committed):
    """Every fixture of every committed case resolves and maps to exactly one tool.

    No network, no key: fixture names and the prefix table only.
    """
    payloads = live_driver.load_fixtures(committed)   # resolves fixtures/<name>
    table = live_driver.fixture_tools(payloads)
    assert set(payloads) == set(committed["fixtures"])
    # One fixture per tool: a second wellness-*.json in one case would silently
    # shadow the first and grade the model with data the case never intended.
    assert len(table) == len(payloads)


def test_tool_args_accepts_a_dict_and_drops_identifiers():
    """Some providers send arguments as an object instead of a JSON string;
    a TypeError there would look like a model failure in the transcript."""
    assert live_driver._tool_args({"function": {"arguments": {"sport": "Ride"}}}) == {"sport": "Ride"}
    assert live_driver._tool_args(
        {"function": {"arguments": '{"sport": "Ride", "discord_id": "123"}'}}
    ) == {"sport": "Ride"}
    assert live_driver._tool_args({"function": {"arguments": "not json"}}) == {}


def test_malformed_reply_exits_instead_of_inventing_a_transcript(monkeypatch):
    """A 200 with no choices must fail loudly: a silent empty transcript would
    score as a model that made no decisions at all."""
    monkeypatch.setenv("HERMES_DRIVER_API_KEY", "test-key")
    monkeypatch.setattr(live_driver, "_post", lambda config, payload: {"id": "x"})
    with pytest.raises(SystemExit) as exc:
        live_driver.drive({"id": "case", "chat_type": "dm", "athlete_message": "hej"},
                          [], {}, live_driver.model_config())
    assert "choices" in str(exc.value)
