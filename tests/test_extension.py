"""Job Finder extension tests — store, settings, CV, chat handlers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from unittest.mock import AsyncMock, patch
from imperal_sdk.testing import MockContext


def _ctx() -> MockContext:
    return MockContext(role="user")


# ─── Settings ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_settings_defaults():
    from app import load_settings, DEFAULT_SETTINGS
    s = await load_settings(_ctx())
    assert s["job_type"] == DEFAULT_SETTINGS["job_type"]
    assert s["jsearch_key"] == ""
    assert s["remote_only"] is False


@pytest.mark.asyncio
async def test_save_and_load_settings():
    from app import save_settings, load_settings
    ctx = _ctx()
    await save_settings(ctx, {"jsearch_key": "abc123", "location": "London"})
    s = await load_settings(ctx)
    assert s["jsearch_key"] == "abc123"
    assert s["location"] == "London"


@pytest.mark.asyncio
async def test_save_settings_generates_user_key():
    from app import save_settings, load_settings
    ctx = _ctx()
    await save_settings(ctx, {"country": "gb"})
    s = await load_settings(ctx)
    assert len(s.get("user_key", "")) == 16


# ─── CV helpers ────────────────────────────────────────

@pytest.mark.asyncio
async def test_cv_ready_false_when_none():
    from app import cv_ready
    assert not cv_ready(None)


@pytest.mark.asyncio
async def test_cv_ready_false_when_empty():
    from app import cv_ready
    assert not cv_ready({"content": "", "description": ""})


@pytest.mark.asyncio
async def test_cv_ready_true_with_content():
    from app import cv_ready
    assert cv_ready({"content": "John Doe, Software Engineer..."})


@pytest.mark.asyncio
async def test_cv_roundtrip():
    from app import save_cv, load_cv
    ctx = _ctx()
    await save_cv(ctx, {"content": "My CV text here", "source": "paste"})
    cv = await load_cv(ctx)
    assert cv is not None
    assert cv["content"] == "My CV text here"
    assert cv["source"] == "paste"


@pytest.mark.asyncio
async def test_cv_update():
    from app import save_cv, load_cv
    ctx = _ctx()
    await save_cv(ctx, {"content": "old", "source": "paste"})
    await save_cv(ctx, {"content": "new", "source": "generated"})
    cv = await load_cv(ctx)
    assert cv["content"] == "new"
    assert cv["source"] == "generated"


# ─── Results helpers ───────────────────────────────────

@pytest.mark.asyncio
async def test_results_none_initially():
    from app import load_results
    assert await load_results(_ctx()) is None


@pytest.mark.asyncio
async def test_results_roundtrip():
    from app import save_results, load_results
    ctx = _ctx()
    jobs = [{"job_id": "1", "title": "Dev", "company": "Acme", "location": "Remote", "match_score": 85}]
    await save_results(ctx, jobs)
    loaded = await load_results(ctx)
    assert loaded is not None
    assert loaded[0]["title"] == "Dev"
    assert loaded[0]["match_score"] == 85


# ─── Chat handlers ─────────────────────────────────────

@pytest.mark.asyncio
async def test_fn_save_cv_success():
    import handlers_jobs
    from params import SaveCVParams
    ctx = _ctx()
    cv_text = "John Doe\nSoftware Engineer with 5 years experience in Python and JavaScript.\n" * 5
    result = await handlers_jobs.fn_save_cv(ctx, SaveCVParams(content=cv_text))
    assert result.status == "success"
    from app import load_cv
    cv = await load_cv(ctx)
    assert cv is not None
    assert cv["source"] == "paste"


@pytest.mark.asyncio
async def test_fn_save_cv_too_short():
    import handlers_jobs
    from params import SaveCVParams
    result = await handlers_jobs.fn_save_cv(_ctx(), SaveCVParams(content="Too short"))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_fn_describe_self_success():
    import handlers_jobs
    from params import DescribeSelfParams
    ctx = _ctx()
    result = await handlers_jobs.fn_describe_self(
        ctx,
        DescribeSelfParams(description="I am a senior backend engineer with 7 years in Python and Go, looking for remote roles."),
    )
    assert result.status == "success"
    from app import load_cv
    cv = await load_cv(ctx)
    assert cv["source"] == "description"


@pytest.mark.asyncio
async def test_fn_describe_self_too_short():
    import handlers_jobs
    from params import DescribeSelfParams
    result = await handlers_jobs.fn_describe_self(_ctx(), DescribeSelfParams(description="Hi"))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_fn_search_jobs_no_key():
    import handlers_jobs
    from params import SearchJobsParams
    result = await handlers_jobs.fn_search_jobs(_ctx(), SearchJobsParams())
    assert result.status == "error"
    assert "API key" in result.error


@pytest.mark.asyncio
async def test_fn_search_jobs_saves_results():
    import handlers_jobs
    from app import save_settings, load_results
    from params import SearchJobsParams
    ctx = _ctx()
    await save_settings(ctx, {"jsearch_key": "test-key"})

    mock_jobs = [
        {"job_id": "j1", "title": "Python Dev", "company": "Acme",
         "location": "Remote", "match_score": 90, "apply_url": "https://example.com/apply"},
    ]
    with patch.object(handlers_jobs, "call_mos", new=AsyncMock(return_value={"jobs": mock_jobs})):
        result = await handlers_jobs.fn_search_jobs(ctx, SearchJobsParams(query="python developer"))

    assert result.status == "success"
    saved = await load_results(ctx)
    assert saved is not None
    assert saved[0]["title"] == "Python Dev"


@pytest.mark.asyncio
async def test_fn_apply_jobs_no_cv():
    import handlers_jobs
    from params import ApplyJobsParams
    result = await handlers_jobs.fn_apply_jobs(_ctx(), ApplyJobsParams(jobs="all"))
    assert result.status == "error"
    assert "CV" in result.error


@pytest.mark.asyncio
async def test_fn_apply_jobs_no_results():
    import handlers_jobs
    from app import save_cv
    from params import ApplyJobsParams
    ctx = _ctx()
    await save_cv(ctx, {"content": "John Doe, Developer " * 20, "source": "paste"})
    result = await handlers_jobs.fn_apply_jobs(ctx, ApplyJobsParams(jobs="all"))
    assert result.status == "error"
    assert "results" in result.error.lower()


@pytest.mark.asyncio
async def test_fn_apply_jobs_max_5():
    import handlers_jobs
    from app import save_cv, save_results
    from params import ApplyJobsParams
    ctx = _ctx()
    await save_cv(ctx, {"content": "Senior Dev. " * 20, "source": "paste"})
    jobs = [
        {"job_id": str(i), "title": f"Job {i}", "company": "Co",
         "location": "Remote", "apply_url": "https://example.com"}
        for i in range(8)
    ]
    await save_results(ctx, jobs)

    mock_apps = [{"title": f"Job {i}", "company": "Co",
                  "apply_url": "https://example.com", "cover_letter": "Dear..."} for i in range(5)]
    mock_fn = AsyncMock(return_value={"applications": mock_apps})
    with patch.object(handlers_jobs, "call_mos", new=mock_fn):
        result = await handlers_jobs.fn_apply_jobs(ctx, ApplyJobsParams(jobs="all", max=5))
        assert result.status == "success"
        call_args = mock_fn.call_args
        assert len(call_args.args[2]["jobs"]) == 5


@pytest.mark.asyncio
async def test_fn_save_settings_persists():
    import handlers_settings
    from app import load_settings
    from params import SaveJobSettingsParams
    ctx = _ctx()
    result = await handlers_settings.fn_save_settings(ctx, SaveJobSettingsParams(
        jsearch_key="my-rapidapi-key",
        location="Berlin",
        job_type="fulltime",
        remote_only=True,
    ))
    assert result.status == "success"
    s = await load_settings(ctx)
    assert s["jsearch_key"] == "my-rapidapi-key"
    assert s["location"] == "Berlin"
    assert s["job_type"] == "fulltime"
    assert s["remote_only"] is True
