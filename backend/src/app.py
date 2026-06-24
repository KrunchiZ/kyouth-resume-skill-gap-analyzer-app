import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from find_skill_gaps import find_skill_gaps_from_text

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "/app/data/jobs.db"))

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
	if body.pdf_content:
		# Run skill-gap analysis
		result = find_skill_gaps_from_text(body.pdf_content, DB_PATH)
		gaps = result.gaps

		# Build a natural-language reply
		if gaps:
			reply = (
				f"I've analyzed your resume against {len(gaps)} job listings. "
				f"Here are the key skill gaps I identified:\n\n"
			)
			# Group gaps by category (or just list them)
			for i, gap in enumerate(gaps, 1):
				reply += f"{i}. {gap}\n"
			reply += "\nTo improve your competitiveness, consider learning or gaining " \
					 f"experience in these areas: {', '.join(gaps[:5])}."
		else:
			reply = (
				"Great news! Your skills align well with the job listings in our database. "
				"I didn't identify any significant skill gaps."
			)

		# If the user also sent a text message, incorporate it
		if body.message:
			reply = f"{body.message}\n\n{reply}"

		return ChatResponse(response=reply, skill_gaps=gaps)

	# Fallback for text-only messages
	return ChatResponse(
		response=f"You said: \"{body.message}\". Upload your resume to get a skill-gap analysis!",
		skill_gaps=[],
	)
