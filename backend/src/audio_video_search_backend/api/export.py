"""POST /export and /export/meta: subtitle draft and transcript of one file (plan 04-09).

Skeleton for the RED step; the routes follow in the GREEN step.
"""

from fastapi import APIRouter

from audio_video_search_backend.subtitles.cues import build_cues

router = APIRouter()

__all__ = ["build_cues", "router"]
