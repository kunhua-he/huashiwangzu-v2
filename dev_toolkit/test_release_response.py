from dev_toolkit.release_response import build_release_gate_response


def test_release_gate_response_does_not_map_debt_to_clean_success() -> None:
    output = 'human\nRELEASE_GATE_JSON: {"verdict": "PASS_WITH_DEBT", "has_debt": true}\n'
    result = build_release_gate_response(
        output=output,
        returncode=0,
        skip_ui=True,
        duration_seconds=1.2345,
    )

    assert result["success"] is False
    assert result["clean_pass"] is False
    assert result["release_safe"] is True
    assert result["has_debt"] is True
    assert result["verdict"] == "PASS_WITH_DEBT"
