from checkpoint_harmony_mcp.tools._common import apply_view


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
