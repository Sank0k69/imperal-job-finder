"""Chat handlers — settings management."""
# No `from __future__ import annotations` — param types must be real at runtime.

from imperal_sdk.types import ActionResult

from app import chat, save_settings
from params import SaveJobSettingsParams


@chat.function(
    "save_job_settings",
    description="Save Job Finder settings: JSearch API key and search filters (location, remote, job type, salary).",
    action_type="write",
    chain_callable=True,
    effects=["update:settings"],
    event="jobfinder.settings.saved",
)
async def fn_save_settings(ctx, params: SaveJobSettingsParams) -> ActionResult:
    updates = {}
    if params.jsearch_key  is not None: updates["jsearch_key"]  = params.jsearch_key.strip()
    if params.remote_only  is not None: updates["remote_only"]  = params.remote_only
    if params.location     is not None: updates["location"]     = params.location.strip()
    if params.job_type     is not None: updates["job_type"]     = params.job_type
    if params.salary_min   is not None: updates["salary_min"]   = params.salary_min
    if params.country      is not None: updates["country"]      = params.country.strip().lower()

    await save_settings(ctx, updates)
    return ActionResult.success(data={}, summary="Settings saved.")
