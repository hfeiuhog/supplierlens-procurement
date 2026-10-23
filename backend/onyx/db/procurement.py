"""Procurement review records stored in the current Onyx schema."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.orm import Session

procurement_metadata = MetaData()
cases = Table(
    "procurement_review",
    procurement_metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_id", String(36), nullable=False),
    Column("request_key", String(80), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("state", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("owner_id", "request_key", name="uq_procurement_owner_request"),
)
events = Table(
    "procurement_review_event",
    procurement_metadata,
    Column("id", String(36), primary_key=True),
    Column("case_id", String(36), ForeignKey("procurement_review.id"), nullable=False),
    Column("actor_id", String(36), nullable=False),
    Column("action", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("note", String(1000), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class ReviewRecord(TypedDict):
    id: str
    owner_id: str
    payload: dict[str, Any]
    payload_hash: str
    state: str
    version: int


class ReviewConflict(ValueError):
    pass


def _view(row: Any) -> ReviewRecord:
    return ReviewRecord(
        id=row.id,
        owner_id=row.owner_id,
        payload=row.payload,
        payload_hash=row.payload_hash,
        state=row.state,
        version=row.version,
    )


def _event(
    session: Session, record: ReviewRecord, actor: str, action: str, note: str
) -> None:
    session.execute(
        insert(events).values(
            id=str(uuid.uuid4()),
            case_id=record["id"],
            actor_id=actor,
            action=action,
            version=record["version"],
            payload_hash=record["payload_hash"],
            note=note,
            created_at=datetime.now(timezone.utc),
        )
    )


def create_review(
    session: Session, owner: str, request_key: str, payload: dict[str, Any]
) -> ReviewRecord:
    digest = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    previous = session.execute(
        select(cases).where(
            cases.c.owner_id == owner, cases.c.request_key == request_key
        )
    ).first()
    if previous:
        if previous.payload_hash != digest:
            raise ReviewConflict("The request key belongs to another payload")
        return _view(previous)
    record = ReviewRecord(
        id=str(uuid.uuid4()),
        owner_id=owner,
        payload=payload,
        payload_hash=digest,
        state="draft",
        version=1,
    )
    session.execute(
        insert(cases).values(
            **record, request_key=request_key, created_at=datetime.now(timezone.utc)
        )
    )
    _event(session, record, owner, "created", "")
    session.commit()
    return record


def get_review(session: Session, case_id: str) -> ReviewRecord:
    row = session.execute(select(cases).where(cases.c.id == case_id)).first()
    if row is None:
        raise KeyError(case_id)
    return _view(row)


def list_reviews(session: Session, limit: int = 50) -> list[ReviewRecord]:
    return [
        _view(row)
        for row in session.execute(
            select(cases).order_by(cases.c.created_at.desc()).limit(min(limit, 100))
        )
    ]


def transition_review(
    session: Session,
    case_id: str,
    actor: str,
    version: int,
    action: Literal["submit", "approve", "reject"],
    note: str,
) -> ReviewRecord:
    record = get_review(session, case_id)
    old_state, new_state = (
        ("draft", "submitted")
        if action == "submit"
        else ("submitted", "approved" if action == "approve" else "rejected")
    )
    if action == "submit" and actor != record["owner_id"]:
        raise PermissionError("Only the author can submit this review")
    if action != "submit" and actor == record["owner_id"]:
        raise PermissionError("A different reviewer must decide this case")
    if action in {"submit", "approve"}:
        from onyx.server.manage.procurement.policy import validate_evidence

        validate_evidence(record["payload"])
    if action == "reject" and not note.strip():
        raise ReviewConflict("A rejection reason is required")
    changed = session.execute(
        update(cases)
        .where(
            cases.c.id == case_id,
            cases.c.version == version,
            cases.c.state == old_state,
        )
        .values(state=new_state, version=version + 1)
    ).rowcount
    if changed != 1:
        session.rollback()
        raise ReviewConflict("The review changed; reload the current version")
    record["state"], record["version"] = new_state, version + 1
    _event(session, record, actor, action, note)
    session.commit()
    return record


def review_audit(session: Session, case_id: str) -> list[dict[str, Any]]:
    get_review(session, case_id)
    rows = session.execute(
        select(
            events.c.actor_id,
            events.c.action,
            events.c.version,
            events.c.payload_hash,
            events.c.note,
        )
        .where(events.c.case_id == case_id)
        .order_by(events.c.created_at, events.c.version)
    )
    return [dict(row._mapping) for row in rows]
