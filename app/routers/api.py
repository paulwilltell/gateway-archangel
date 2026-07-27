from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.analysis.engine import analysis_to_dict, analyze_target
from app.archangel_chat import ChatUnavailableError, run_chat_turn
from app.models import Analysis, AuditEvent, ContentReport, Post, Reply, utcnow
from app.routers.common import (
    enforce_content_policy,
    enforce_rate_limit,
    get_or_create_user,
    record_consent,
    require_moderator,
)
from app.ownership import new_token, token_matches
from app.schemas import ChatRequest, OwnershipAction, PostCreate, PostOut, ReplyCreate, ReportCreate

router = APIRouter(prefix="/api/v1", tags=["api"])


def _run_analysis(request: Request, target_type: str, target_id: str) -> None:
    with request.app.state.db.session() as db:
        analyze_target(db, request.app.state.settings, target_type, target_id)


@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": "gateway-archangel",
        "engine_version": request.app.state.settings.archangel_engine_version,
        "corpus_version": request.app.state.settings.corpus_version,
        "analyzer": request.app.state.settings.archangel_analyzer,
    }


@router.get("/posts", response_model=list[PostOut])
def list_posts(request: Request):
    with request.app.state.db.session() as db:
        return db.scalars(
            select(Post)
            .options(joinedload(Post.author), selectinload(Post.replies).joinedload(Reply.author))
            .where(Post.status == "published", Post.visibility == "public")
            .order_by(Post.created_at.desc())
        ).unique().all()


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(request: Request, payload: PostCreate, background_tasks: BackgroundTasks):
    settings = request.app.state.settings
    if len(payload.body) > settings.max_post_chars:
        raise HTTPException(422, "Post exceeds configured maximum length")
    enforce_rate_limit(request, "post")
    enforce_content_policy(payload.title, payload.body)
    owner_token, owner_hash = new_token()
    with request.app.state.db.session() as db:
        user = get_or_create_user(db, payload.author_name)
        post = Post(
            author_id=user.id,
            title=payload.title,
            body=payload.body,
            training_consent=payload.training_consent,
            owner_token_hash=owner_hash,
        )
        db.add(post)
        db.flush()
        record_consent(
            db,
            user_id=user.id,
            target_type="post",
            target_id=post.id,
            consented=payload.training_consent,
            policy_version=settings.training_policy_version,
        )
        post_id = post.id
    background_tasks.add_task(_run_analysis, request, "post", post_id)
    return {
        "id": post_id,
        "analysis_status": "queued",
        "owner_token": owner_token,
        "owner_token_notice": (
            "Save this token. It is shown once and is the only way to withdraw this "
            "post or its research consent later — there are no accounts to recover it with."
        ),
    }


@router.post("/posts/{post_id}/replies", status_code=status.HTTP_201_CREATED)
def create_reply(request: Request, post_id: str, payload: ReplyCreate, background_tasks: BackgroundTasks):
    settings = request.app.state.settings
    if len(payload.body) > settings.max_reply_chars:
        raise HTTPException(422, "Reply exceeds configured maximum length")
    enforce_rate_limit(request, "reply")
    enforce_content_policy(payload.body)
    owner_token, owner_hash = new_token()
    with request.app.state.db.session() as db:
        post = db.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Post not found")
        user = get_or_create_user(db, payload.author_name)
        reply = Reply(
            post_id=post_id,
            author_id=user.id,
            body=payload.body,
            training_consent=payload.training_consent,
            owner_token_hash=owner_hash,
        )
        db.add(reply)
        db.flush()
        record_consent(
            db,
            user_id=user.id,
            target_type="reply",
            target_id=reply.id,
            consented=payload.training_consent,
            policy_version=settings.training_policy_version,
        )
        reply_id = reply.id
    background_tasks.add_task(_run_analysis, request, "reply", reply_id)
    return {"id": reply_id, "analysis_status": "queued", "owner_token": owner_token}


@router.get("/analysis/{target_type}/{target_id}")
def get_analysis(request: Request, target_type: str, target_id: str):
    if target_type not in {"post", "reply"}:
        raise HTTPException(422, "target_type must be post or reply")
    with request.app.state.db.session() as db:
        row = db.scalar(
            select(Analysis)
            .where(Analysis.target_type == target_type, Analysis.target_id == target_id)
            .order_by(Analysis.created_at.desc())
        )
        if not row:
            raise HTTPException(404, "Analysis not found")
        return analysis_to_dict(row)


@router.post("/ownership/{target_type}/{target_id}/withdraw")
def withdraw_content(request: Request, target_type: str, target_id: str, payload: OwnershipAction):
    """Withdraw your own post or reply using the ownership token you were
    shown when you published it. No account exists to prove authorship;
    possession of the token is the proof. See app/ownership.py."""
    if target_type not in {"post", "reply"}:
        raise HTTPException(422, "target_type must be post or reply")
    with request.app.state.db.session() as db:
        model = Post if target_type == "post" else Reply
        target = db.get(model, target_id)
        if not target:
            raise HTTPException(404, "Content not found")
        if not token_matches(payload.owner_token, target.owner_token_hash):
            raise HTTPException(403, "That ownership token does not match this content.")
        if payload.action == "delete":
            target.status = "withdrawn_by_author"
            target.training_consent = False
        else:
            target.training_consent = False
        db.add(
            AuditEvent(
                event_type=f"author_{payload.action}",
                actor_type="author",
                target_type=target_type,
                target_id=target_id,
                details_json=json.dumps({"action": payload.action}),
            )
        )
        return {"id": target_id, "action": payload.action, "status": target.status}


@router.post("/archangel/chat")
def archangel_chat(request: Request, payload: ChatRequest):
    """One conversation turn with Archangel.

    Stateless by design: the client resends its own history each turn and the
    server persists nothing — no conversation table exists. See
    docs/ANTI_SURVEILLANCE_POLICY.md.
    """
    enforce_rate_limit(request, "chat")
    with request.app.state.db.session() as db:
        try:
            result = run_chat_turn(
                db,
                request.app.state.settings,
                [m.model_dump() for m in payload.messages],
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except ChatUnavailableError as exc:
            raise HTTPException(503, str(exc))
    return {
        "reply": result.reply,
        "evidence": result.evidence,
        "citations": result.citations,
        "model": result.model,
        "safety": {
            "level": result.safety.level,
            "category": result.safety.category,
            "display_message": result.safety.display_message,
            "resources": list(result.safety.resources),
        },
    }


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(request: Request, payload: ReportCreate):
    """Anyone may report content. Reports are content-first: no reporter or
    author identity is recorded."""
    enforce_rate_limit(request, "report")
    with request.app.state.db.session() as db:
        model = Post if payload.target_type == "post" else Reply
        if not db.get(model, payload.target_id):
            raise HTTPException(404, "Content not found")
        report = ContentReport(
            target_type=payload.target_type,
            target_id=payload.target_id,
            category=payload.category,
            details=payload.details,
            source="human",
        )
        db.add(report)
        db.flush()
        db.add(
            AuditEvent(
                event_type="content_reported",
                target_type=payload.target_type,
                target_id=payload.target_id,
                details_json=json.dumps({"category": payload.category, "report_id": report.id}),
            )
        )
        return {"id": report.id, "status": "open"}


@router.get("/moderation/reports")
def list_open_reports(request: Request):
    require_moderator(request)
    with request.app.state.db.session() as db:
        reports = db.scalars(
            select(ContentReport)
            .where(ContentReport.status == "open")
            .order_by(ContentReport.created_at.asc())
        ).all()
        result = []
        for report in reports:
            model = Post if report.target_type == "post" else Reply
            target = db.get(model, report.target_id)
            excerpt = ""
            target_status = "missing"
            if target:
                text = f"{target.title}\n{target.body}" if report.target_type == "post" else target.body
                excerpt = text[:400]
                target_status = target.status
            result.append(
                {
                    "id": report.id,
                    "target_type": report.target_type,
                    "target_id": report.target_id,
                    "category": report.category,
                    "details": report.details,
                    "source": report.source,
                    "created_at": report.created_at.isoformat(),
                    "content_excerpt": excerpt,
                    "content_status": target_status,
                }
            )
        return result


def _moderate(request: Request, target_type: str, target_id: str, new_status: str, resolution: str) -> dict:
    require_moderator(request)
    if target_type not in {"post", "reply"}:
        raise HTTPException(422, "target_type must be post or reply")
    with request.app.state.db.session() as db:
        model = Post if target_type == "post" else Reply
        target = db.get(model, target_id)
        if not target:
            raise HTTPException(404, "Content not found")
        target.status = new_status
        open_reports = db.scalars(
            select(ContentReport).where(
                ContentReport.target_type == target_type,
                ContentReport.target_id == target_id,
                ContentReport.status == "open",
            )
        ).all()
        for report in open_reports:
            report.status = "resolved"
            report.resolution = resolution
            report.resolved_at = utcnow()
        db.add(
            AuditEvent(
                event_type=f"content_{resolution}",
                actor_type="moderator",
                target_type=target_type,
                target_id=target_id,
                details_json=json.dumps({"reports_resolved": len(open_reports)}),
            )
        )
        return {"id": target_id, "status": new_status, "reports_resolved": len(open_reports)}


@router.post("/moderation/{target_type}/{target_id}/remove")
def remove_content(request: Request, target_type: str, target_id: str):
    """Remove content for a policy violation (sexual/abusive/spam/illegal only —
    never viewpoint). Content is hidden, not deleted: the record remains for audit."""
    return _moderate(request, target_type, target_id, new_status="removed", resolution="removed")


@router.post("/moderation/{target_type}/{target_id}/restore")
def restore_content(request: Request, target_type: str, target_id: str):
    return _moderate(request, target_type, target_id, new_status="published", resolution="dismissed")


@router.post("/analysis/{target_type}/{target_id}/rerun")
def rerun_analysis(request: Request, target_type: str, target_id: str):
    if target_type not in {"post", "reply"}:
        raise HTTPException(422, "target_type must be post or reply")
    with request.app.state.db.session() as db:
        try:
            row = analyze_target(db, request.app.state.settings, target_type, target_id, force=True)
        except LookupError:
            raise HTTPException(404, "Target not found")
        return analysis_to_dict(row)
