from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.analysis.engine import analysis_to_dict, analyze_target
from app.models import Analysis, AuditEvent, ContentReport, Post, Reply
from app.display import alignment_label, split_claims, support_label
from app.hermeneutic import HERMENEUTIC_RULESET_VERSION, published_rules
from app.ownership import new_token
from app.policy import POLICY_CATEGORIES
from app.routers.common import (
    anonymous_pseudonym,
    enforce_content_policy,
    enforce_rate_limit,
    get_or_create_user,
    record_consent,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
# Reader-facing wording and ordering live in app/display.py, deliberately
# separate from the engine's internal vocabulary.
templates.env.filters["support_label"] = support_label
templates.env.filters["alignment_label"] = alignment_label
templates.env.filters["split_claims"] = split_claims


def _run_analysis(request: Request, target_type: str, target_id: str) -> None:
    db_factory = request.app.state.db
    settings = request.app.state.settings
    with db_factory.session() as db:
        analyze_target(db, settings, target_type, target_id)


def _latest_analysis_map(db, targets: list[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    for target_type, target_id in targets:
        row = db.scalar(
            select(Analysis)
            .where(Analysis.target_type == target_type, Analysis.target_id == target_id)
            .order_by(Analysis.created_at.desc())
        )
        if row:
            result[(target_type, target_id)] = analysis_to_dict(row) or {}
    return result


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    with request.app.state.db.session() as db:
        posts = db.scalars(
            select(Post)
            .options(joinedload(Post.author), selectinload(Post.replies))
            .where(Post.status == "published", Post.visibility == "public")
            .order_by(Post.created_at.desc())
            .limit(30)
        ).unique().all()
        targets = [("post", post.id) for post in posts]
        analyses = _latest_analysis_map(db, targets)
        pending_count = db.scalar(
            select(func.count()).select_from(Analysis).where(Analysis.status != "completed")
        ) or 0
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "posts": posts,
                "analyses": analyses,
                "pending_count": pending_count,
                "settings": request.app.state.settings,
            },
        )


@router.post("/posts")
def create_post(
    request: Request,
    background_tasks: BackgroundTasks,
    author_name: str = Form(""),
    title: str = Form(...),
    body: str = Form(...),
    training_consent: bool = Form(False),
    post_anonymously: bool = Form(False),
):
    settings = request.app.state.settings
    author_name = author_name.strip()
    title = title.strip()
    body = body.strip()
    if not post_anonymously and not (2 <= len(author_name) <= 80):
        raise HTTPException(422, "Display name must be 2–80 characters (or post anonymously)")
    if not (5 <= len(title) <= 180):
        raise HTTPException(422, "Title must be 5–180 characters")
    if not (10 <= len(body) <= settings.max_post_chars):
        raise HTTPException(422, f"Post must be 10–{settings.max_post_chars} characters")
    enforce_rate_limit(request, "post")
    enforce_content_policy(title, body)

    owner_token, owner_hash = new_token()
    with request.app.state.db.session() as db:
        if post_anonymously:
            author_name = anonymous_pseudonym(db)
        user = get_or_create_user(db, author_name)
        post = Post(
            owner_token_hash=owner_hash,
            author_id=user.id,
            title=title,
            body=body,
            training_consent=training_consent,
        )
        db.add(post)
        db.flush()
        record_consent(
            db,
            user_id=user.id,
            target_type="post",
            target_id=post.id,
            consented=training_consent,
            policy_version=settings.training_policy_version,
        )
        post_id = post.id

    background_tasks.add_task(_run_analysis, request, "post", post_id)
    # Rendered directly rather than redirected: an ownership token in a URL
    # would persist in browser history and referrer headers.
    return _render_post(request, post_id, owner_token=owner_token)


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def post_detail(request: Request, post_id: str):
    return _render_post(request, post_id)


def _render_post(request: Request, post_id: str, owner_token: str | None = None):
    with request.app.state.db.session() as db:
        post = db.scalar(
            select(Post)
            .options(joinedload(Post.author), selectinload(Post.replies).joinedload(Reply.author))
            .where(Post.id == post_id, Post.status == "published")
        )
        if not post:
            raise HTTPException(404, "Post not found")
        replies = post.published_replies
        targets = [("post", post.id), *[("reply", reply.id) for reply in replies]]
        analyses = _latest_analysis_map(db, targets)
        return templates.TemplateResponse(
            request=request,
            name="post.html",
            context={
                "post": post,
                "replies": replies,
                "analyses": analyses,
                "settings": request.app.state.settings,
                "reported": request.query_params.get("reported") == "1",
                "owner_token": owner_token,
            },
        )


@router.post("/posts/{post_id}/replies")
def create_reply(
    request: Request,
    background_tasks: BackgroundTasks,
    post_id: str,
    author_name: str = Form(""),
    body: str = Form(...),
    training_consent: bool = Form(False),
    post_anonymously: bool = Form(False),
):
    settings = request.app.state.settings
    author_name = author_name.strip()
    body = body.strip()
    if not post_anonymously and not (2 <= len(author_name) <= 80):
        raise HTTPException(422, "Display name must be 2–80 characters (or post anonymously)")
    if not (2 <= len(body) <= settings.max_reply_chars):
        raise HTTPException(422, f"Reply must be 2–{settings.max_reply_chars} characters")
    enforce_rate_limit(request, "reply")
    enforce_content_policy(body)

    reply_owner_token, reply_owner_hash = new_token()
    with request.app.state.db.session() as db:
        post = db.get(Post, post_id)
        if not post or post.status != "published":
            raise HTTPException(404, "Post not found")
        if post_anonymously:
            author_name = anonymous_pseudonym(db)
        user = get_or_create_user(db, author_name)
        reply = Reply(
            owner_token_hash=reply_owner_hash,
            post_id=post_id,
            author_id=user.id,
            body=body,
            training_consent=training_consent,
        )
        db.add(reply)
        db.flush()
        record_consent(
            db,
            user_id=user.id,
            target_type="reply",
            target_id=reply.id,
            consented=training_consent,
            policy_version=settings.training_policy_version,
        )
        reply_id = reply.id

    background_tasks.add_task(_run_analysis, request, "reply", reply_id)
    return _render_post(request, post_id, owner_token=reply_owner_token)


@router.post("/posts/{post_id}/report")
def report_post(
    request: Request,
    post_id: str,
    category: str = Form(...),
    details: str = Form(""),
):
    if category not in set(POLICY_CATEGORIES):
        raise HTTPException(422, "Unknown report category")
    enforce_rate_limit(request, "report")
    with request.app.state.db.session() as db:
        post = db.get(Post, post_id)
        if not post:
            raise HTTPException(404, "Post not found")
        report = ContentReport(
            target_type="post",
            target_id=post_id,
            category=category,
            details=details.strip()[:2000] or None,
            source="human",
        )
        db.add(report)
        db.flush()
        db.add(
            AuditEvent(
                event_type="content_reported",
                target_type="post",
                target_id=post_id,
                details_json=json.dumps({"category": category, "report_id": report.id}),
            )
        )
    return RedirectResponse(url=f"/posts/{post_id}?reported=1", status_code=303)


@router.get("/archangel", response_class=HTMLResponse)
def archangel_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="archangel.html",
        context={"settings": request.app.state.settings},
    )


@router.get("/method", response_class=HTMLResponse)
def method_page(request: Request):
    registry_path = Path(request.app.state.settings.source_registry_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else []
    return templates.TemplateResponse(
        request=request,
        name="method.html",
        context={
            "registry": registry,
            "settings": request.app.state.settings,
            "hermeneutic_rules": published_rules(),
            "ruleset_version": HERMENEUTIC_RULESET_VERSION,
        },
    )


@router.get("/data-consent", response_class=HTMLResponse)
def data_consent_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="data_consent.html",
        context={"settings": request.app.state.settings},
    )
