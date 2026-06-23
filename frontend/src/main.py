import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Resume Helper Frontend")

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
	backend_url = os.getenv("BACKEND_URL", "http://localhost:8001")
	return templates.TemplateResponse(
		request=request,
		name="chat_page.html",
		context={"backend_url": backend_url},
	)


@app.get("/health")
async def health():
	return {"status": "ok"}