import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Resume Helper Backend")

# Allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    pdf_content: Optional[str] = None
    timestamp: str


class ChatResponse(BaseModel):
    response: str
    skill_gaps: list[str] = []


# ── Routes ────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.

    TODO (Day 3):
      1. If body.pdf_content is set, parse the resume text.
      2. Run Week 2 skill-gap analysis against the SQLite DB from Week 1.
      3. Use an LLM (or rule-based logic) to produce a natural-language reply.
      4. Return the reply + skill gap list.
    """
    # ── Placeholder until Day 3 ───────────────────────────────
    if body.pdf_content:
        reply = (
            "I've received your resume! "
            "Full skill-gap analysis will be wired up on Day 3. "
            "Stay tuned."
        )
    else:
        reply = (
            f"You said: \"{body.message}\". "
            "The backend is running — full AI responses coming on Day 3!"
        )

    return ChatResponse(response=reply, skill_gaps=[])
