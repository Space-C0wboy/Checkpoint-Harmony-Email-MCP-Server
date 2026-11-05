from checkpoint_harmony_mcp.tools._common import (
    apply_view,
    clean_description,
    normalize_task_status,
    record_matches,
)


def _double(r):
    return {"id": r["id"]}


def test_compacts_and_preserves_envelope():
    resp = {
        "responseEnvelope": {"recordsNumber": 9, "scrollId": "S1"},
        "responseData": [{"id": 1, "big": "x"}, {"id": 2, "big": "y"}],
    }
    out = apply_view(resp, limit=25, full=False, compactor=_double)
    assert out["responseEnvelope"] == {"recordsNumber": 9, "scrollId": "S1"}
    assert out["responseData"] == [{"id": 1}, {"id": 2}]


def test_limit_truncates():
    resp = {"responseData": [{"id": 1}, {"id": 2}, {"id": 3}]}
    out = apply_view(resp, limit=2, full=True, compactor=_double)
    assert out["responseData"] == [{"id": 1}, {"id": 2}]


def test_nonpositive_limit_returns_empty_not_negative_slice():
    resp = {"responseData": [{"id": 1}, {"id": 2}, {"id": 3}]}
    assert apply_view(resp, limit=0, full=True, compactor=_double)["responseData"] == []
    assert apply_view(resp, limit=-1, full=True, compactor=_double)["responseData"] == []


def test_full_returns_records_verbatim():
    resp = {"responseData": [{"id": 1, "big": "x"}]}
    out = apply_view(resp, limit=25, full=True, compactor=_double)
    assert out["responseData"] == [{"id": 1, "big": "x"}]


def test_empty_passthrough_unchanged():
    assert apply_view({"responseData": []}, 25, False, _double) == {"responseData": []}


def test_missing_response_data_unchanged():
    assert apply_view({"foo": "bar"}, 25, False, _double) == {"foo": "bar"}


def test_does_not_mutate_input():
    resp = {"responseData": [{"id": 1, "big": "x"}]}
    apply_view(resp, 25, False, _double)
    assert resp["responseData"][0] == {"id": 1, "big": "x"}


def test_clean_description_extracts_labels():
    raw = 'User #{"display": "embedded-entity", "label": "alice@x.com"} reported #{"label": "Phishing", "entity_type": "scan"}'
    assert clean_description(raw) == "User alice@x.com reported Phishing"


def test_clean_description_passes_plain_text():
    assert clean_description("no tokens here") == "no tokens here"
    assert clean_description(None) is None


def test_record_matches_and_semantics():
    assert record_matches([("Hello World", "hello", "contains"), ("A@B.com", "a@b.com", "exact")])
    assert not record_matches([("Hello", "bye", "contains")])
    assert record_matches([(["x@y.com", "z@y.com"], "Z@Y.com", "in")])
    assert not record_matches([(["x@y.com"], "q@y.com", "in")])


def test_normalize_task_status():
    inprog = {
        "responseData": {
            "actions": [{"action_name": "Q", "action_status": "completed", "action_message": "ok"}],
            "status": "inprogress",
        }
    }
    assert normalize_task_status(inprog)["status"] == "completed"
    failed = {
        "responseData": {"actions": [{"action_status": "completed"}, {"action_status": "failed"}]}
    }
    assert normalize_task_status(failed)["status"] == "failed"
    pending = {"responseData": {"actions": [{"action_status": "init"}]}}
    assert normalize_task_status(pending)["status"] == "inprogress"
    assert normalize_task_status(inprog)["raw"] is inprog
