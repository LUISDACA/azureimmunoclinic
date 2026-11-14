"""Offline migration comparison tests using synthetic-only fixtures."""

import copy
import json
from pathlib import Path

import pytest
from validation.legacy_compare import compare_legacy_exports

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_synthetic_legacy_fixtures_compare_without_changes():
    before = _fixture("t03_legacy_before.json")
    after = _fixture("t03_legacy_after.json")

    report = compare_legacy_exports(before, after)

    assert before["synthetic_only"] and after["synthetic_only"]
    assert report["valid"] is True
    assert report["issue_count"] == 0
    assert report["before_counts"] == {
        "assignments": 2,
        "doses": 3,
        "evidence": 2,
        "eligibility": 1,
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("loss", "RECORD_LOST"),
        ("addition", "RECORD_ADDED"),
        ("status", "STATUS_CHANGED"),
        ("date", "APPLICATION_DATE_CHANGED"),
        ("review", "REVIEWER_CHANGED"),
        ("review_date", "REVIEW_DATE_CHANGED"),
        ("duplicate", "DUPLICATE_OR_MISSING_ID"),
        ("bad_association", "ASSOCIATION_OWNER_MISMATCH"),
        ("missing_association", "ASSOCIATION_TARGET_MISSING"),
        ("duplicate_dose_key", "DUPLICATE_DOSE_KEY"),
        ("eligibility", "ELIGIBILITY_CHANGED"),
    ],
)
def test_validator_reports_legacy_invariant_breaks_without_values(mutation, expected):
    before = _fixture("t03_legacy_before.json")
    after = copy.deepcopy(before)
    if mutation == "loss":
        after["records"]["doses"].pop(0)
    elif mutation == "addition":
        after["records"]["assignments"].append(
            {"id": "synthetic-new", "owner_id": "student-a", "vaccine_code": "NEW"}
        )
    elif mutation == "status":
        after["records"]["doses"][0]["status"] = "denied"
    elif mutation == "date":
        after["records"]["doses"][0]["applied_date"] = "2014-03-01"
    elif mutation == "review":
        after["records"]["doses"][0]["reviewed_by"] = None
    elif mutation == "review_date":
        after["records"]["doses"][0]["reviewed_at"] = None
    elif mutation == "duplicate":
        after["records"]["doses"].append(copy.deepcopy(after["records"]["doses"][0]))
    elif mutation == "bad_association":
        after["records"]["evidence"][0]["dose_id"] = "dose-old"
        after["records"]["evidence"][0]["owner_id"] = "student-b"
    elif mutation == "missing_association":
        after["records"]["evidence"][0]["dose_id"] = "missing-dose"
    elif mutation == "duplicate_dose_key":
        duplicate = copy.deepcopy(after["records"]["doses"][0])
        duplicate["id"] = "synthetic-duplicate-dose"
        after["records"]["doses"].append(duplicate)
    elif mutation == "eligibility":
        after["records"]["eligibility"][0]["is_certifiable"] = True

    report = compare_legacy_exports(before, after)

    assert report["valid"] is False
    assert expected in {issue["code"] for issue in report["issues"]}
    if mutation == "duplicate":
        assert report["after_counts"]["doses"] == 4
    serialized = json.dumps(report)
    assert "2014-03-01" not in serialized
    assert "student-a" not in serialized


def test_partial_doses_without_complete_semantic_key_are_not_reported_as_duplicates():
    before = _fixture("t03_legacy_before.json")
    after = copy.deepcopy(before)
    partial = {
        "id": "synthetic-partial-dose",
        "owner_id": "student-a",
        "assignment_id": "assign-partial",
        "dose_number": None,
        "status": "pending",
    }
    after["records"]["doses"].append(partial)

    report = compare_legacy_exports(before, after)

    codes = {issue["code"] for issue in report["issues"]}
    assert "RECORD_ADDED" in codes
    assert "DUPLICATE_DOSE_KEY" not in codes


def test_t02_profile_fixture_has_all_reconciliation_triggers():
    fixture = _fixture("t02_profile_changes.json")
    assert fixture["synthetic_only"] is True
    assert {case["field"] for case in fixture["cases"]} == {"sex", "program", "campus"}
