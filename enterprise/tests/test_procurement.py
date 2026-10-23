import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from onyx.db.procurement import (
    ReviewConflict,
    create_review,
    get_review,
    procurement_metadata,
    review_audit,
    transition_review,
)
from onyx.server.manage.procurement import policy


@pytest.fixture
def engine():
    value = create_engine(os.environ["TEST_DATABASE_URL"])
    procurement_metadata.drop_all(value)
    procurement_metadata.create_all(value)
    yield value
    procurement_metadata.drop_all(value)
    value.dispose()


@pytest.fixture
def payload():
    return {
        "vendor_ref": "SYN-VENDOR",
        "tender_ref": "SYN-TENDER",
        "requirements": [{"key": "license", "label": "License", "mandatory": True}],
        "evidence": [
            {
                "requirement_key": "license",
                "document_ref": "SYN-DOC",
                "version": "v1",
                "quote": "Synthetic license",
                "valid_until": "2099-01-01T00:00:00Z",
            }
        ],
    }


def test_valid_evidence_and_expiry_boundary(payload):
    policy.validate_evidence(payload, datetime(2098, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        policy.validate_evidence(payload, datetime(2099, 1, 1, tzinfo=timezone.utc))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(evidence=[]),
        lambda p: p["evidence"][0].update(valid_until="2000-01-01T00:00:00Z"),
        lambda p: p["evidence"][0].update(valid_until="2099-01-01T00:00:00"),
        lambda p: p["requirements"].append(dict(p["requirements"][0])),
        lambda p: p["evidence"][0].update(requirement_key="unknown"),
    ],
)
def test_invalid_or_missing_evidence_is_blocked(payload, mutate):
    mutate(payload)
    with pytest.raises(ValueError):
        policy.validate_evidence(payload)


def test_create_replay_and_payload_conflict(engine, payload):
    with Session(engine) as session:
        first = create_review(session, "author", "request-key", payload)
        assert (
            create_review(session, "author", "request-key", payload)["id"]
            == first["id"]
        )
        with pytest.raises(ReviewConflict):
            create_review(
                session, "author", "request-key", {**payload, "vendor_ref": "other"}
            )
        assert len(review_audit(session, first["id"])) == 1


def test_author_and_independent_reviewer(engine, payload):
    with Session(engine) as session:
        record = create_review(session, "author", "request-key", payload)
        with pytest.raises(PermissionError):
            transition_review(session, record["id"], "other", 1, "submit", "")
        transition_review(session, record["id"], "author", 1, "submit", "")
        with pytest.raises(PermissionError):
            transition_review(session, record["id"], "author", 2, "approve", "")
        approved = transition_review(
            session, record["id"], "reviewer", 2, "approve", "Checked"
        )
        assert approved["state"] == "approved"
        events = review_audit(session, record["id"])
        assert [e["action"] for e in events] == ["created", "submit", "approve"]
        assert len({e["payload_hash"] for e in events}) == 1


def test_concurrent_decisions_have_one_winner(engine, payload):
    with Session(engine) as session:
        record = create_review(session, "author", "request-key", payload)
        transition_review(session, record["id"], "author", 1, "submit", "")

    def decide(actor):
        with Session(engine) as session:
            try:
                transition_review(session, record["id"], actor, 2, "approve", "Checked")
                return "won"
            except ReviewConflict:
                return "conflict"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(decide, ["reviewer-a", "reviewer-b"])) == [
            "conflict",
            "won",
        ]
    with Session(engine) as session:
        assert len(review_audit(session, record["id"])) == 3


def test_approval_rechecks_expiry(engine, payload, monkeypatch):
    with Session(engine) as session:
        record = create_review(session, "author", "request-key", payload)
        transition_review(session, record["id"], "author", 1, "submit", "")

        class FutureClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2100, 1, 1, tzinfo=timezone.utc)

        monkeypatch.setattr(policy, "datetime", FutureClock)
        with pytest.raises(ValueError):
            transition_review(session, record["id"], "reviewer", 2, "approve", "")
        assert get_review(session, record["id"])["state"] == "submitted"


def test_rejection_needs_a_reason(engine, payload):
    with Session(engine) as session:
        record = create_review(session, "author", "request-key", payload)
        transition_review(session, record["id"], "author", 1, "submit", "")
        with pytest.raises(ReviewConflict):
            transition_review(session, record["id"], "reviewer", 2, "reject", "")
        assert (
            transition_review(
                session,
                record["id"],
                "reviewer",
                2,
                "reject",
                "Missing supplier assurance",
            )["state"]
            == "rejected"
        )
