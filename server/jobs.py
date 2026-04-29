"""MOS service — job search via JSearch (RapidAPI) + AI matching and cover letter generation.

Deploy to VPS: copy to marketing-os/server/services/jobs.py
Add to main.py: from services.jobs import router as jobs_router; app.include_router(jobs_router)
"""
from __future__ import annotations

import httpx
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import ANTHROPIC_API_KEY, CONTENT_MODEL

router = APIRouter(prefix="/api/jobs")
_ai    = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"

_MATCH_TOOL = {
    "name": "jobs",
    "description": "Return ranked job matches with AI scores",
    "input_schema": {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "job_id":          {"type": "string"},
                        "title":           {"type": "string"},
                        "company":         {"type": "string"},
                        "location":        {"type": "string"},
                        "employment_type": {"type": "string"},
                        "is_remote":       {"type": "boolean"},
                        "salary":          {"type": "string"},
                        "snippet":         {"type": "string"},
                        "apply_url":       {"type": "string"},
                        "match_score":     {"type": "integer"},
                        "match_reason":    {"type": "string"},
                    },
                    "required": ["job_id", "title", "company", "location", "match_score", "apply_url"],
                },
            },
        },
        "required": ["jobs"],
    },
}

_APPLY_TOOL = {
    "name": "applications",
    "description": "Return personalized cover letters for each job",
    "input_schema": {
        "type": "object",
        "properties": {
            "applications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title":        {"type": "string"},
                        "company":      {"type": "string"},
                        "apply_url":    {"type": "string"},
                        "cover_letter": {"type": "string"},
                    },
                    "required": ["title", "company", "apply_url", "cover_letter"],
                },
            },
        },
        "required": ["applications"],
    },
}


class SearchRequest(BaseModel):
    user_key:    str
    jsearch_key: str
    query:       Optional[str]  = ""
    remote_only: Optional[bool] = False
    location:    Optional[str]  = ""
    job_type:    Optional[str]  = "any"
    salary_min:  Optional[int]  = 0
    country:     Optional[str]  = "us"
    cv_text:     Optional[str]  = ""


class ApplyRequest(BaseModel):
    user_key: str
    jobs:     list
    cv_text:  str


def _salary_str(job: dict) -> str:
    lo  = job.get("job_min_salary")
    hi  = job.get("job_max_salary")
    cur = job.get("job_salary_currency", "USD")
    if lo and hi:
        return f"{cur} {int(lo):,}–{int(hi):,}/yr"
    if lo:
        return f"{cur} {int(lo):,}+/yr"
    return ""


async def _fetch_jsearch(key: str, query: str, remote_only: bool,
                         location: str, job_type: str, country: str) -> list[dict]:
    params: dict = {
        "query":     query or "software engineer",
        "page":      "1",
        "num_pages": "2",
        "country":   country or "us",
        "language":  "en_gb",
    }
    if remote_only:
        params["remote_jobs_only"] = "true"
    if location:
        params["location"] = location
    if job_type and job_type != "any":
        params["employment_types"] = job_type.upper()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            JSEARCH_URL,
            params=params,
            headers={
                "X-RapidAPI-Key":  key,
                "X-RapidAPI-Host": JSEARCH_HOST,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"JSearch error {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("data", [])


@router.post("/search")
async def search_jobs(req: SearchRequest):
    raw = await _fetch_jsearch(
        req.jsearch_key,
        req.query or "",
        req.remote_only or False,
        req.location or "",
        req.job_type or "any",
        req.country or "us",
    )
    if not raw:
        return {"jobs": []}

    jobs_text = "\n\n".join(
        f"ID: {j.get('job_id','')}\n"
        f"Title: {j.get('job_title','')}\n"
        f"Company: {j.get('employer_name','')}\n"
        f"Location: {j.get('job_city','')}, {j.get('job_country','')}\n"
        f"Remote: {j.get('job_is_remote', False)}\n"
        f"Type: {j.get('job_employment_type','')}\n"
        f"Salary: {_salary_str(j)}\n"
        f"Description: {(j.get('job_description') or '')[:400]}"
        for j in raw[:20]
    )
    cv_section = f"\n\nCandidate CV:\n{req.cv_text[:3000]}" if req.cv_text else "\n\nNo CV provided — rank by relevance only."

    msg = await _ai.messages.create(
        model=CONTENT_MODEL,
        max_tokens=4000,
        tools=[_MATCH_TOOL],
        tool_choice={"type": "tool", "name": "jobs"},
        messages=[{
            "role": "user",
            "content": (
                "Score and rank these job listings by match to the candidate's CV. "
                "Return top 10. For each: match_score 0-100, one-sentence match_reason, "
                "apply_url from the job data, and a 2-sentence snippet summarising the role.\n\n"
                f"Jobs:\n{jobs_text}{cv_section}"
            ),
        }],
    )

    for block in msg.content:
        if block.type == "tool_use" and block.name == "jobs":
            return {"jobs": block.input.get("jobs", [])}

    return {"jobs": [], "error": "AI ranking failed"}


@router.post("/apply")
async def apply_jobs(req: ApplyRequest):
    if not req.jobs:
        return {"applications": []}

    jobs_text = "\n\n".join(
        f"Position: {j.get('title','')}\n"
        f"Company: {j.get('company','')}\n"
        f"Apply URL: {j.get('apply_url','N/A')}\n"
        f"About the role: {j.get('snippet','')}"
        for j in req.jobs[:5]
    )

    msg = await _ai.messages.create(
        model=CONTENT_MODEL,
        max_tokens=6000,
        tools=[_APPLY_TOOL],
        tool_choice={"type": "tool", "name": "applications"},
        messages=[{
            "role": "user",
            "content": (
                "Write a personalized cover letter for each job. "
                "Each letter: 150-200 words, professional tone, specific to the company and role, "
                "reference relevant experience from the CV. Start with a strong hook.\n\n"
                f"Candidate CV:\n{req.cv_text[:3000]}\n\n"
                f"Jobs:\n{jobs_text}"
            ),
        }],
    )

    for block in msg.content:
        if block.type == "tool_use" and block.name == "applications":
            return {"applications": block.input.get("applications", [])}

    return {"applications": [], "error": "Cover letter generation failed"}
