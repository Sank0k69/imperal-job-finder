"""Parameter models for Job Finder chat functions.

No `from __future__ import annotations` — the SDK validator reads
type annotations at runtime via inspect.signature.
"""
from pydantic import BaseModel
from typing import Optional


class SaveJobSettingsParams(BaseModel):
    jsearch_key: Optional[str]  = None
    remote_only: Optional[bool] = None
    location:    Optional[str]  = None
    job_type:    Optional[str]  = None   # any | fulltime | parttime | contractor | intern
    salary_min:  Optional[int]  = None
    country:     Optional[str]  = None


class SaveCVParams(BaseModel):
    content: str   # pasted CV text (plain or markdown)


class DescribeSelfParams(BaseModel):
    description: str   # voice transcript or typed self-description


class GenerateCVParams(BaseModel):
    tone: Optional[str] = None   # professional | creative | technical


class SearchJobsParams(BaseModel):
    query:       Optional[str]  = None   # job title / skills override
    remote_only: Optional[bool] = None
    location:    Optional[str]  = None
    job_type:    Optional[str]  = None


class SaveJobParams(BaseModel):
    job_id:   str
    title:    str
    company:  str
    location: str
    url:      str
    score:    Optional[int] = None


class ApplyJobsParams(BaseModel):
    jobs: Optional[str] = None   # "1,2,3" or "all" — positions from last results
    max:  Optional[int] = 5
