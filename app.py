"""Job Finder extension — core init + shared store helpers."""
from __future__ import annotations

import uuid
from imperal_sdk import Extension, ChatExtension

SERVER_URL     = "https://mos.lexa-lox.xyz"
SERVER_API_KEY = "dd5f08814b30d05ff8b573231a14a6826c39d7c07f226995c9a8b1573ceebb90"

ext = Extension("job-finder", version="1.0.0")
chat = ChatExtension(
    ext,
    tool_name="job_finder",
    description=(
        "Job Finder - search jobs matching your CV, get AI match scores, "
        "generate a polished CV from your description, and apply with cover letters. "
        "Ask to search jobs, upload CV, describe yourself, or apply to positions."
    ),
    max_rounds=8,
)

SETTINGS_COLLECTION = "jobfinder_settings"
CV_COLLECTION       = "jobfinder_cv"
RESULTS_COLLECTION  = "jobfinder_results"
SAVED_COLLECTION    = "jobfinder_saved"

DEFAULT_SETTINGS: dict = {
    "jsearch_key": "",
    "user_key":    "",
    "remote_only": False,
    "location":    "",
    "job_type":    "any",     # any | fulltime | parttime | contractor | intern
    "salary_min":  0,
    "country":     "us",
}


async def load_settings(ctx) -> dict:
    try:
        page = await ctx.store.query(SETTINGS_COLLECTION, limit=1)
    except Exception:
        return dict(DEFAULT_SETTINGS)
    docs = getattr(page, "data", None) or []
    if docs and isinstance(getattr(docs[0], "data", None), dict):
        return {**DEFAULT_SETTINGS, **docs[0].data}
    return dict(DEFAULT_SETTINGS)


async def save_settings(ctx, values: dict) -> dict:
    current = await load_settings(ctx)
    merged = {**current, **{k: v for k, v in values.items() if v is not None}}
    if not merged.get("user_key"):
        merged["user_key"] = uuid.uuid4().hex[:16]
    page = await ctx.store.query(SETTINGS_COLLECTION, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(SETTINGS_COLLECTION, docs[0].id, merged)
    else:
        await ctx.store.create(SETTINGS_COLLECTION, merged)
    return merged


async def load_cv(ctx) -> dict | None:
    try:
        page = await ctx.store.query(CV_COLLECTION, limit=1)
    except Exception:
        return None
    docs = getattr(page, "data", None) or []
    if docs and isinstance(getattr(docs[0], "data", None), dict):
        return docs[0].data
    return None


async def save_cv(ctx, cv_data: dict) -> None:
    page = await ctx.store.query(CV_COLLECTION, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(CV_COLLECTION, docs[0].id, cv_data)
    else:
        await ctx.store.create(CV_COLLECTION, cv_data)


async def load_results(ctx) -> list | None:
    try:
        page = await ctx.store.query(RESULTS_COLLECTION, limit=1)
    except Exception:
        return None
    docs = getattr(page, "data", None) or []
    if docs and isinstance(getattr(docs[0], "data", None), dict):
        return docs[0].data.get("jobs")
    return None


async def save_results(ctx, jobs: list) -> None:
    page = await ctx.store.query(RESULTS_COLLECTION, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(RESULTS_COLLECTION, docs[0].id, {"jobs": jobs})
    else:
        await ctx.store.create(RESULTS_COLLECTION, {"jobs": jobs})


async def load_saved_jobs(ctx) -> list:
    try:
        page = await ctx.store.query(SAVED_COLLECTION, limit=50)
    except Exception:
        return []
    docs = getattr(page, "data", None) or []
    return [d.data for d in docs if isinstance(getattr(d, "data", None), dict)]


async def save_job_bookmark(ctx, job: dict) -> None:
    await ctx.store.create(SAVED_COLLECTION, job)


def cv_ready(cv: dict | None) -> bool:
    return bool(cv and (cv.get("content") or cv.get("description")))
