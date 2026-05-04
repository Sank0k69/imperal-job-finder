"""Chat handlers — CV, job search and cover letter applications."""
# No `from __future__ import annotations` — param types must be real at runtime.

from imperal_sdk.types import ActionResult

from app import (
    chat, load_settings, save_cv, load_cv,
    save_results, load_results, save_job_bookmark, cv_ready,
)
from api_client import call_mos
from params import (
    SaveCVParams, DescribeSelfParams, GenerateCVParams,
    SearchJobsParams, SaveJobParams, ApplyJobsParams,
)


def _err(data: dict) -> ActionResult:
    return ActionResult.error(error=data.get("error", "Server error. Please try again."))


@chat.function(
    "save_cv",
    description=(
        "Save the user's CV. Use when they paste their resume, upload CV text, "
        "or say 'here is my CV' / 'this is my resume'."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:cv"],
    event="jobfinder.cv.saved",
)
async def fn_save_cv(ctx, params: SaveCVParams) -> ActionResult:
    if len(params.content.strip()) < 100:
        return ActionResult.error(error="CV seems too short. Paste your full resume text.")
    await save_cv(ctx, {"content": params.content.strip(), "source": "paste"})
    return ActionResult.success(
        data={},
        summary="CV saved. You can now search for jobs or ask me to improve it.",
    )


@chat.function(
    "describe_self",
    description=(
        "Let the user describe themselves in free text (or voice transcription). "
        "Saves the description and offers to generate a structured CV. "
        "Use when they say 'let me tell you about myself', describe experience verbally, "
        "or want to create a CV without an existing resume."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:cv"],
    event="jobfinder.cv.saved",
)
async def fn_describe_self(ctx, params: DescribeSelfParams) -> ActionResult:
    if len(params.description.strip()) < 50:
        return ActionResult.error(error="Description too short. Tell me more about your experience, skills and goals.")
    await save_cv(ctx, {"description": params.description.strip(), "source": "description", "content": ""})
    return ActionResult.success(
        data={},
        summary=(
            "Got it! Description saved. "
            "You can say 'generate my CV' to create a polished resume, or just search for jobs now."
        ),
    )


@chat.function(
    "generate_cv",
    description=(
        "Generate a professional CV from the user's description or refine their existing CV. "
        "Use when they ask to 'generate my CV', 'create my resume', or 'improve my CV'."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:cv"],
    event="jobfinder.cv.saved",
)
async def fn_generate_cv(ctx, params: GenerateCVParams) -> ActionResult:
    cv = await load_cv(ctx)
    if not cv:
        return ActionResult.error(error="No CV or description found. Paste your CV or describe your experience first.")

    source_text = cv.get("content") or cv.get("description", "")
    if not source_text:
        return ActionResult.error(error="Nothing to work with. Save your CV or description first.")

    data = await call_mos(ctx, "/api/resume/generate", {
        "source_text": source_text,
        "source_type": cv.get("source", "paste"),
        "tone":        params.tone or "professional",
    })
    if "error" in data:
        return _err(data)

    await save_cv(ctx, {
        **cv,
        "content": data.get("cv_text", source_text),
        "source":  "generated",
        "summary": data.get("summary", ""),
    })
    return ActionResult.success(
        data={},
        summary=f"CV generated!\n\n{data.get('cv_text', '')}",
    )


@chat.function(
    "search_jobs",
    description=(
        "Search for jobs matching the user's CV and filters via JSearch (RapidAPI aggregator — "
        "LinkedIn, Indeed, Glassdoor and more). "
        "Use when they say 'find jobs', 'search for work', 'what jobs match my profile', etc. "
        "Requires JSearch API key in Settings."
    ),
    action_type="read",
    event="jobfinder.results.ready",
)
async def fn_search_jobs(ctx, params: SearchJobsParams) -> ActionResult:
    s = await load_settings(ctx)
    if not s.get("jsearch_key"):
        return ActionResult.error(error="JSearch API key not set. Open Settings and add your RapidAPI key.")

    cv = await load_cv(ctx)
    cv_text = (cv.get("content") or cv.get("description", "")) if cv else ""

    data = await call_mos(ctx, "/api/jobs/search", {
        "jsearch_key": s["jsearch_key"],
        "query":       params.query or "",
        "remote_only": params.remote_only if params.remote_only is not None else s.get("remote_only", False),
        "location":    params.location or s.get("location", ""),
        "job_type":    params.job_type or s.get("job_type", "any"),
        "salary_min":  s.get("salary_min", 0),
        "country":     s.get("country", "us"),
        "cv_text":     cv_text,
    })
    if "error" in data:
        return _err(data)

    jobs = data.get("jobs", [])
    await save_results(ctx, jobs)

    lines = [
        f"{i+1}. {j['title']} @ {j['company']} — {j.get('location','')} — match: {j.get('match_score','?')}%"
        for i, j in enumerate(jobs[:10])
    ]
    return ActionResult.success(
        data=data,
        summary=(
            f"Found {len(jobs)} matching positions:\n" + "\n".join(lines)
            if lines else "No matching jobs found. Try adjusting your filters or search query."
        ),
    )


@chat.function(
    "save_job",
    description="Bookmark a job from search results to the saved list.",
    action_type="write",
    chain_callable=True,
    effects=["create:saved_job"],
    event="jobfinder.job.saved",
)
async def fn_save_job(ctx, params: SaveJobParams) -> ActionResult:
    await save_job_bookmark(ctx, {
        "job_id":   params.job_id,
        "title":    params.title,
        "company":  params.company,
        "location": params.location,
        "url":      params.url,
        "score":    params.score,
    })
    return ActionResult.success(data={}, summary=f"Saved: {params.title} @ {params.company}.")


@chat.function(
    "apply_jobs",
    description=(
        "Generate personalized cover letters for matched jobs and prepare applications. "
        "Use when the user says 'apply', 'send applications', 'apply to the top 5', etc. "
        "Accepts job numbers like '1,2,3' or 'all'. Max 5 per request."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:application"],
    event="jobfinder.applied",
)
async def fn_apply_jobs(ctx, params: ApplyJobsParams) -> ActionResult:
    cv = await load_cv(ctx)
    if not cv_ready(cv):
        return ActionResult.error(error="No CV found. Add your resume or describe yourself first.")

    results = await load_results(ctx)
    if not results:
        return ActionResult.error(error="No job results found. Search for jobs first.")

    max_apply = min(params.max or 5, 5)
    selected: list
    if not params.jobs or params.jobs.strip().lower() == "all":
        selected = results[:max_apply]
    else:
        indices = []
        for part in params.jobs.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(results):
                    indices.append(idx)
        selected = [results[i] for i in indices[:max_apply]]

    if not selected:
        return ActionResult.error(error="Could not identify jobs to apply to. Say '1,2,3' or 'all'.")

    cv_text = cv.get("content") or cv.get("description", "")
    data = await call_mos(ctx, "/api/jobs/apply", {
        "jobs":    selected,
        "cv_text": cv_text,
    })
    if "error" in data:
        return _err(data)

    applications = data.get("applications", [])
    lines = [
        f"**{app['title']} @ {app['company']}**\n"
        f"Apply: {app.get('apply_url','N/A')}\n\n"
        f"{app.get('cover_letter','')}"
        for app in applications
    ]
    return ActionResult.success(
        data=data,
        summary=(
            f"{len(applications)} cover letter(s) ready:\n\n"
            + "\n\n---\n\n".join(lines)
        ),
    )
