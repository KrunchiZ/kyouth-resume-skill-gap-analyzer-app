import os
import time
import httpx
from pathlib import Path
from collections import defaultdict
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")

app = FastAPI(title="Resume Helper Frontend")

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

# ── Request / Response models ──────────────────────────────────
class ChatRequest(BaseModel):
	message: str
	pdf_content: Optional[str] = None
	timestamp: str

class ChatResponse(BaseModel):
	response: str
	skill_gaps: list[str] = []


# ── Rate Limiter ───────────────────────────────────────────────
# Sliding-window per-client limiter.
# Uses the backend's rate_limits.txt to derive a safe request cap
# from the LLM's token-per-minute budget.

_RATE_LIMITS_TXT = Path(__file__).parent / "rate_limits.txt"
_WINDOW_SECONDS = 60  # sliding window size

_request_timestamps: dict[str, list[float]] = defaultdict(list)


def _parse_num(s: str) -> int:
	s = s.upper().replace(",", "")
	if s.endswith("M"):
		return int(float(s[:-1]) * 1_000_000)
	if s.endswith("K"):
		return int(float(s[:-1]) * 1_000)
	return int(s)


def _load_rate_limits(path: Path) -> dict[str, dict]:
	limits: dict[str, dict] = {}
	if not path.exists():
		return limits
	for line in path.read_text().splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		parts = line.split()
		if len(parts) < 4:
			continue
		model, rpm_s, *_ = parts
		limits[model] = {"rpm": _parse_num(rpm_s)}
	return limits


def _get_proxy_rpm() -> int:
	"""Derive a safe proxy-level RPM from the LLM's TPM budget.

	Each chat request sends one resume → one LLM call.
	We conservatively allow 1 request per 10 RPM of the model
	to stay well within the LLM's token budget.
	"""
	limits = _load_rate_limits(_RATE_LIMITS_TXT)
	# Default to a safe fallback if we can't read rate limits
	default_rpm = 10
	if not limits:
		return default_rpm

	# Use the first (default) model's RPM
	first_rpm = next(iter(limits.values())).get("rpm", default_rpm * 10)
	return max(default_rpm, first_rpm // 10)


_PROXY_RPM = _get_proxy_rpm()


def _check_rate_limit(client_ip: str) -> None:
	"""Raise 429 if the client has exceeded the allowed requests."""
	now = time.time()
	window_start = now - _WINDOW_SECONDS

	# Prune old entries outside the sliding window
	ts_list = _request_timestamps[client_ip]
	_request_timestamps[client_ip] = [t for t in ts_list if t > window_start]

	if len(_request_timestamps[client_ip]) >= _PROXY_RPM:
		raise HTTPException(
			status_code=429,
			detail=f"Rate limit exceeded. Max {_PROXY_RPM} requests per {_WINDOW_SECONDS}s.",
		)

	_request_timestamps[client_ip].append(now)


# ── Routes ─────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
	return templates.TemplateResponse(
		request=request,
		name="chat_page.html",
	)


@app.post("/api/chat", response_model=ChatResponse)
async def proxy_chat(request: Request, body: ChatRequest) -> ChatResponse:
	# Enforce rate limit before forwarding
	_check_rate_limit(request.client.host if request.client else "unknown")

	async with httpx.AsyncClient() as client:
		resp = await client.post(
			f"{BACKEND_URL}/api/chat",
			json=body.model_dump(),
			timeout=120.0,  # LLM calls can take a while
		)
	resp.raise_for_status()
	return ChatResponse(**resp.json())


@app.get("/health")
async def health():
	return {"status": "ok"}