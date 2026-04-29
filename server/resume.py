"""MOS service — CV generation from free-text or voice description.

Deploy to VPS: copy to marketing-os/server/services/resume.py
Add to main.py: from services.resume import router as resume_router; app.include_router(resume_router)
"""
from __future__ import annotations

import anthropic
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from config import ANTHROPIC_API_KEY, CONTENT_MODEL

router = APIRouter(prefix="/api/resume")
_ai    = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

_CV_TOOL = {
    "name": "cv",
    "description": "Return a structured, formatted CV",
    "input_schema": {
        "type": "object",
        "properties": {
            "cv_text": {
                "type": "string",
                "description": "Full CV in clean Markdown — sections: Summary, Experience, Skills, Education",
            },
            "summary": {
                "type": "string",
                "description": "One-paragraph professional summary, 80-100 words",
            },
        },
        "required": ["cv_text", "summary"],
    },
}

_TONE_MAP = {
    "professional": "formal and professional",
    "creative":     "creative and engaging",
    "technical":    "technically precise and detailed",
}


class ResumeRequest(BaseModel):
    user_key:    str
    source_text: str
    source_type: Optional[str] = "paste"          # paste | description | generated
    tone:        Optional[str] = "professional"


@router.post("/generate")
async def generate_cv(req: ResumeRequest):
    tone_desc = _TONE_MAP.get(req.tone or "professional", "formal and professional")
    action = (
        "Transform this self-description into a polished CV."
        if req.source_type == "description"
        else "Reformat and improve this CV, fixing structure and language."
    )

    msg = await _ai.messages.create(
        model=CONTENT_MODEL,
        max_tokens=3000,
        tools=[_CV_TOOL],
        tool_choice={"type": "tool", "name": "cv"},
        messages=[{
            "role": "user",
            "content": (
                f"{action} "
                f"Tone: {tone_desc}. "
                "Output clean Markdown with sections: Summary, Experience, Skills, Education. "
                "Keep concise — 1 page equivalent. No fluff.\n\n"
                f"Input:\n{req.source_text[:4000]}"
            ),
        }],
    )

    for block in msg.content:
        if block.type == "tool_use" and block.name == "cv":
            return block.input

    return {"error": "CV generation failed", "cv_text": req.source_text, "summary": ""}
