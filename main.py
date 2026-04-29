"""Job Finder extension — entry point with module hot-reload."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in (
        "app", "api_client", "params",
        "handlers_jobs", "handlers_settings",
        "panels_main", "panels_side",
    ):
        del sys.modules[_m]

from app import ext, chat  # noqa: E402, F401

import handlers_jobs      # noqa: E402, F401
import handlers_settings  # noqa: E402, F401
import panels_main        # noqa: E402, F401
import panels_side        # noqa: E402, F401


@ext.on_install
async def on_install(ctx):
    from imperal_sdk.types import ActionResult
    return ActionResult.success(
        summary=(
            "Job Finder installed! "
            "Open Settings to add your JSearch API key and paste your CV — "
            "then ask Webbee to find you matching jobs."
        ),
    )


@ext.health_check
async def health(ctx):
    from imperal_sdk.types import ActionResult
    from app import load_settings, load_cv, cv_ready
    s  = await load_settings(ctx)
    cv = await load_cv(ctx)
    return ActionResult.success(data={
        "version":        "1.0.0",
        "api_configured": bool(s.get("jsearch_key")),
        "cv_ready":       cv_ready(cv),
    })
