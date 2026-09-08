#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "research" / "kimi-agent-benchmark.json"
REPORT_PATH = ROOT / "en" / "research" / "kimi-code-agent-benchmark.mdx"


def close(actual: float, expected: float, tolerance: float = 1e-8) -> None:
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance):
        raise AssertionError(f"{actual} != {expected}")


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    calls = data["calls"]
    billing = data["billing_at_experiment_time"]
    assert data["schema_version"] == 1
    assert [call["index"] for call in calls] == list(range(1, 7))
    assert all(call["status_code"] == 200 for call in calls)

    prompt_rate = billing["prompt_credits_per_million"]
    completion_rate = billing["completion_credits_per_million"]
    ratio = billing["applied_ratio"]
    for call in calls:
        calculated = 1e-6 * (
            prompt_rate * call["prompt_tokens"] + completion_rate * call["completion_tokens"]
        )
        close(calculated, call["list_credits"])
        close(call["list_credits"] * ratio, call["deducted_credits"])

    close(sum(call["list_credits"] for call in calls), 5.5824156)
    close(sum(call["deducted_credits"] for call in calls), 5.13582235)
    close(
        sum(call["deducted_credits"] for call in calls) * billing["credit_usd_rate"],
        0.48900732505524996,
    )
    assert sum(call["cached_tokens"] for call in calls) == 116032

    task = data["task"]
    close(sum(task["expected_regions"].values()), task["expected_total_revenue"])
    assert task["valid_rows"] + task["skipped_rows"] == task["input_rows"]
    assert task["agent_steps"] == 6
    assert task["tool_calls"] == 5

    report = REPORT_PATH.read_text()
    for expected in (
        "116,032",
        "5.5824156 historical list Credits",
        "5.13582235 deducted Credits",
        "$0.489007",
        "not current pricing",
        "cannot be rerun from this repository",
    ):
        assert expected in report, f"report is missing {expected!r}"
    print("Kimi agent benchmark ledger verified: 6 calls, token math and billing reconcile")


if __name__ == "__main__":
    main()
