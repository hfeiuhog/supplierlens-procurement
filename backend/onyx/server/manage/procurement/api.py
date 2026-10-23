from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.db.procurement import (
    ReviewConflict,
    ReviewRecord,
    create_review,
    get_review,
    list_reviews,
    review_audit,
    transition_review,
)
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.manage.procurement.policy import Decision, ReviewInput

router = APIRouter(prefix="/admin/procurement", tags=["procurement"])
Admin = Annotated[User, Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS))]
Database = Annotated[Session, Depends(get_session)]


@router.get("")
def read_reviews(user: Admin, db: Database) -> list[ReviewRecord]:
    return list_reviews(db)


@router.post("")
def add_review(
    payload: ReviewInput,
    user: Admin,
    db: Database,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=80)],
) -> ReviewRecord:
    try:
        return create_review(
            db, str(user.id), idempotency_key, payload.model_dump(mode="json")
        )
    except (ReviewConflict, IntegrityError) as exc:
        db.rollback()
        raise OnyxError(
            OnyxErrorCode.CONFLICT, "Request key conflict; reload before retry"
        ) from exc


@router.get("/{case_id}")
def read_review(case_id: str, user: Admin, db: Database) -> ReviewRecord:
    try:
        return get_review(db, case_id)
    except KeyError as exc:
        raise OnyxError(OnyxErrorCode.NOT_FOUND) from exc


@router.post("/{case_id}/decision")
def decide(case_id: str, body: Decision, user: Admin, db: Database) -> ReviewRecord:
    try:
        return transition_review(
            db, case_id, str(user.id), body.version, body.action, body.note
        )
    except KeyError as exc:
        raise OnyxError(OnyxErrorCode.NOT_FOUND) from exc
    except PermissionError as exc:
        raise OnyxError(OnyxErrorCode.INSUFFICIENT_PERMISSIONS, str(exc)) from exc
    except ReviewConflict as exc:
        raise OnyxError(OnyxErrorCode.CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(exc)) from exc


@router.get("/{case_id}/audit")
def audit(case_id: str, user: Admin, db: Database) -> list[dict[str, Any]]:
    try:
        return review_audit(db, case_id)
    except KeyError as exc:
        raise OnyxError(OnyxErrorCode.NOT_FOUND) from exc
