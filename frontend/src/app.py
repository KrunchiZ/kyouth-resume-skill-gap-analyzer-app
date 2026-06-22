from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles

app = FastAPI()

# app.mount("/static", StaticFiles(directory="static"), name="static")

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="chat_page.html",
    )
