"""HTTP client — all calls go through the MOS server."""
from __future__ import annotations

from app import SERVER_URL, SERVER_API_KEY, load_settings

TIMEOUT = 90


async def call_mos(ctx, endpoint: str, payload: dict) -> dict:
    s = await load_settings(ctx)
    resp = await ctx.http.post(
        f"{SERVER_URL.rstrip('/')}{endpoint}",
        json={"user_key": s.get("user_key", ""), **payload},
        headers={"X-API-Key": SERVER_API_KEY},
        timeout=TIMEOUT,
    )
    if not resp.ok:
        try:
            body = resp.text()[:300]
        except Exception:
            body = ""
        return {"error": f"server {resp.status_code}: {body}"}
    return resp.json()
