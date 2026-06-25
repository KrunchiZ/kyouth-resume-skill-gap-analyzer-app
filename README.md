# Resume Helper — Skill Gap Analyzer App

A full-stack chat application that analyzes a user's resume against a database of job listings to identify skill gaps, powered by AI models. Built as Week 3 of a 3-week project spanning ETL pipelines, AI integration, and containerization.

---

## Project Overview

This application enables users to upload a PDF resume and receive personalized career advice through a conversational chat interface. The system:

- **Extracts** technical skills from the uploaded resume using an LLM
- **Compares** those skills against tech stacks extracted from job listings stored in a SQLite database
- **Identifies** skill gaps — technologies employers want that the user lacks
- **Answers** general questions about the resume using conversational AI

The architecture consists of three containerized services: a **frontend** (chat UI + reverse proxy), a **backend** (API + AI logic), and an **Ollama** instance (local LLM serving).

---

## Setup Instructions

### Prerequisites

- **Docker** and **Docker Compose** (v2) installed and running
- **Ollama model** — at least one model must be pulled before first use (e.g., `llama3.1`, `gemma3:1b`, `gemini-3.1-flash-lite` via API key)
- **GPU (optional)** — for faster local inference, install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) and uncomment the GPU reservation in `docker-compose.yml`

### Quick Start (Docker Compose)

1. **Clone and navigate** to the project directory:

   ```bash
   cd week3
   ```

2. **Configure environment variables**:

   Copy the example `.env` file and fill in your values:

   ```bash
   cp .env.example .env
   ```

   At minimum, set:

   | Variable | Description | Example |
   |----------|-------------|---------|
   | `BACKEND_URL` | Internal Docker network URL for backend | `http://backend:8001` |
   | `GEMINI_API_KEY` | API key for Gemini models (used for chat responses) | Leave blank if using only Ollama |

   > **Security note:** Never commit your `.env` file. It is listed in `.gitignore`. The `.env.example` file contains placeholder values.

3. **Pull an Ollama model** (run once before starting):

   ```bash
   docker compose run --rm ollama ollama pull llama3.1
   ```

   Alternatively, the backend will auto-pull when it first requests the model.

4. **Build and start**:

   ```bash
   docker compose up --build -d
   ```

   This builds the frontend and backend images, starts three containers (`resume-frontend`, `resume-backend`, `resume-ollama`), and connects them on a shared `app-net` network.

5. **Access the application**:

   Open your browser to [`http://localhost:8000`](http://localhost:8000).

### Manual Setup (without Docker)

If you prefer to run services locally:

1. **Install Python 3.14+** and [`uv`](https://docs.astral.sh/uv/)

2. **Start Ollama** locally (download from [ollama.com](https://ollama.com)):

   ```bash
   ollama pull llama3.1
   ```

3. **Set up the backend**:

   ```bash
   cd backend
   uv sync
   # Set environment variables:
   export DB_PATH=/path/to/your/data/jobs.db
   uv run uvicorn src.app:app --host 0.0.0.0 --port 8001
   ```

4. **Set up the frontend**:

   ```bash
   cd frontend
   uv sync
   export BACKEND_URL=http://localhost:8001
   uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

---

## Usage

### Starting the Application

```bash
docker compose up --build -d
```

### Accessing the Chat Interface

- **Frontend**: [`http://localhost:8000`](http://localhost:8000)
- **Backend API**: `http://localhost:8001` (accessible internally by the frontend)
- **Health check**: `http://localhost:8001/health` → `{"status": "ok"}`

### Interacting with the Chatbot

1. **Upload a resume**: Click the paperclip icon to select a PDF file. The frontend extracts text client-side using PDF.js. A file badge appears above the input bar confirming the upload.

2. **Ask questions**: Type a message and press Enter or click Send.

3. **Skill gap analysis**: Ask questions like *"What skills am I missing?"*, *"Compare my resume"*, or *"Recommend improvements"* to trigger the skill gap analysis. The system will:
   - Extract technical skills from your resume via LLM
   - Fetch tech stacks from all tagged job listings in the database
   - Compute the set difference (job skills − your skills)
   - Return a numbered list of gaps with improvement suggestions

4. **General chat**: Questions unrelated to skill gaps (e.g., *"Summarize my resume"*) are handled by the LLM with your resume text in context.

### Expected Inputs and Outputs

| Input | Output |
|-------|--------|
| PDF resume (≤ 10 MB) | Extracted text sent to backend |
| Text message | Natural-language response from LLM |
| Skill gap query + resume | Numbered list of missing skills + advice |

### Stopping and Cleaning Up

```bash
# Stop all containers
docker compose down

# Stop and remove volumes (deletes Ollama models)
docker compose down -v
```

---

## API / Function Reference

### Backend API

#### `GET /health`

Returns the backend health status.

- **Response**: `{"status": "ok"}`

#### `POST /api/chat`

Main chat endpoint. Accepts a user message and optionally a resume, routes to the appropriate AI pipeline, and returns a response.

- **Request body** (`ChatRequest`):

  ```json
  {
    "message": "What skills am I missing?",
    "pdf_content": "John Doe\nSoftware Engineer\nPython, JavaScript, React...",
    "timestamp": "2025-01-15T10:30:00Z"
  }
  ```

  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `message` | `string` | Yes | User's text input |
  | `pdf_content` | `string \| null` | No | Extracted resume text (sent when a PDF is uploaded) |
  | `timestamp` | `string` | Yes | ISO 8601 timestamp |

- **Response** (`ChatResponse`):

  ```json
  {
    "response": "I've analyzed your resume against 150 job listings. Here are the key skill gaps:\n\n1. Docker\n2. Kubernetes\n3. Terraform\n\nTo improve your competitiveness, consider learning or gaining experience in these areas.",
    "skill_gaps": ["Docker", "Kubernetes", "Terraform"]
  }
  ```

  | Field | Type | Description |
  |-------|------|-------------|
  | `response` | `string` | Natural-language reply from the LLM |
  | `skill_gaps` | `list[string]` | List of identified skill gaps (empty if not a gap query) |

- **Routing logic** (in `src/app.py`):

  1. `_is_skill_gap_intent(message)` — Uses Gemma 3:1B (via Ollama) to classify whether the message is asking about skill gaps. Returns `True`/`False`.
  2. If skill gap query + resume → calls `find_skill_gaps_from_text()` → feeds gap data + user message to Gemini for a contextual response.
  3. If resume + general question → feeds resume + message to Gemini for conversational response.
  4. If no resume → uses Gemma 3:1B for a general response (requests a resume politely).

### Backend Core Functions

#### `find_skill_gaps_from_text(resume_text, db_path)` — `find_skill_gaps.py:142`

Async function that performs the skill gap analysis:

1. Calls `_call_llm()` with the resume text to extract technical skills (using `SYSTEM_PROMPT` + Gemini/Ollama)
2. Connects to the SQLite database via MCP (`db_server.py`)
3. Fetches tagged job listings in batches using `fetch_tagged_jobs`
4. Computes `gaps = job_skills - resume_skills` via set difference
5. Returns a `SkillGapResult(gaps=sorted_list)`

#### `prompt_model(model, prompt, temperature, top_p)` — `prompt_model.py:54`

Unified LLM interface supporting both Ollama and Gemini models:

- Routes to `ollama.Client.generate()` for Ollama models
- Routes to `genai.Client.models.generate_content()` for Gemini models
- Includes retry logic (3 attempts with exponential backoff: 2s, 4s, 8s)
- Returns `None` on failure

#### `db_server.py` — FastMCP Server

Exposes SQLite operations as MCP tools:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `count_jobs()` | — | Returns total job count |
| `count_avg_desc_length()` | — | Returns average description length |
| `fetch_untagged_jobs(batch_size)` | `batch_size: int` | Returns untagged jobs for processing |
| `fetch_tagged_jobs(batch_size, last_sid)` | `batch_size: int`, `last_sid: int` | Returns tagged jobs in pagination order |
| `update_tech_stack(source_id, tech_stack)` | `source_id: str`, `tech_stack: str` | Writes extracted tech stack to a job |

### Frontend Functions

#### `extractPDFText(file)` — `chat_page.html`

Uses PDF.js to read a PDF file client-side and extract text from all pages.

```javascript
async function extractPDFText(file) {
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
  let text = "";
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    text += content.items.map(item => item.str).join(" ") + "\n";
  }
  return text.trim();
}
```

#### `sendMessage()` — `chat_page.html`

Handles the full send flow:

1. Validates that either a message or PDF is present
2. Appends a user bubble (text + file badge if PDF was uploaded) to the chat history
3. Shows a typing indicator
4. POSTs `{message, pdf_content, timestamp}` to `/api/chat`
5. Renders the bot response bubble
6. Clears the PDF state after sending

#### `proxy_chat()` — `frontend/src/main.py:118`

The frontend's reverse proxy route:

1. Enforces rate limiting (sliding window) if a PDF is attached
2. Forwards the request to the backend at `$BACKEND_URL/api/chat` via `httpx`
3. Deserializes the response into a `ChatResponse` Pydantic model
4. Returns it to the frontend

### Docker Network Communication

The three services communicate over the `app-net` bridge network:

```
Browser (host) ──port 8000──▶ resume-frontend ──http://backend:8001──▶ resume-backend
                                                            │
                                                    http://ollama:11434
                                                            │
                                                    resume-ollama (LLM)
```

- The frontend proxies all `/api/chat` requests to the backend using the Docker service name `backend` (DNS-resolved by Docker Compose)
- The backend connects to Ollama at `http://ollama:11434` (the Ollama container's service name)
- The backend spawns `db_server.py` as a subprocess via MCP stdio transport for SQLite queries

---

## Data / Assumptions

### Data Flow

```
User uploads PDF → Browser extracts text (PDF.js)
       ↓
Frontend POSTs {message, pdf_content} to /api/chat
       ↓
Frontend proxy validates rate limit, forwards to backend
       ↓
Backend classifies intent (skill gap query?)
       ↓
If skill gap:
  LLM extracts skills from resume text
  MCP client queries SQLite for tagged job tech stacks
  Set difference computes gaps
  Gemini formats natural-language response with gap data
If general:
  Resume text + user message sent to LLM
  LLM generates contextual response
       ↓
Response flows back through proxy to browser
```

### Data Structures

**SQLite database** (`jobs.db`):

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | TEXT PK | Unique job listing identifier |
| `job_title` | TEXT NOT NULL | Job title |
| `company` | TEXT NOT NULL | Company name |
| `description` | TEXT NOT NULL | Job description |
| `tech_stack` | TEXT | Comma-separated tags (e.g., "Python, Docker, AWS") |
| `quality` | TEXT | Data quality flag ('HIGH'/'LOW') |
| `content_hash` | TEXT | SHA256 hash for deduplication |

**ChatRequest / ChatResponse** — Shared between frontend and backend via Pydantic models, serialized to JSON over HTTP.

### Assumptions and Constraints

- **PDF format**: Only text-based PDFs are supported. Scanned/image PDFs cannot be read by PDF.js.
- **PDF size**: Limited to 10 MB by frontend validation.
- **Message length**: No explicit limit, but very long messages may exceed LLM context windows.
- **Database**: The SQLite database must contain jobs with populated `tech_stack` columns. Un-tagged jobs (NULL `tech_stack`) are skipped during gap analysis.
- **LLM availability**: The system requires either a running Ollama instance (for local models) or a valid `GEMINI_API_KEY` (for cloud models). If both are unavailable, responses will fail gracefully.
- **Single-user rate limits**: The proxy rate limiter uses in-memory storage per process. In a multi-container deployment, rate limits are not coordinated across instances.
- **No conversation history**: Each request is stateless. The LLM only sees the current message + resume text, not previous exchanges.
- **Model selection**: Skill gap classification uses Gemma 3:1B (fast, low-cost). Resume chat uses Gemini 3.1 Flash Lite. General chat without resume uses Gemma 3:1B.

---

## Testing

### Backend Testing

Test the `/api/chat` endpoint directly with `curl`:

```bash
# Health check
curl http://localhost:8001/health

# General chat (no resume)
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "pdf_content": null, "timestamp": "2025-01-01T00:00:00Z"}'

# Skill gap query (with resume text)
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What skills am I missing?",
    "pdf_content": "Python developer with 3 years experience in Django, SQL, and Git.",
    "timestamp": "2025-01-01T00:00:00Z"
  }'
```

Expected response:

```json
{
  "response": "I've analyzed your resume against 150 job listings. Here are the key skill gaps:\n\n1. Docker\n2. Kubernetes\n...",
  "skill_gaps": ["Docker", "Kubernetes", "React"]
}
```

### Frontend Testing

1. Navigate to `http://localhost:8000`
2. **Upload a PDF**: Click the paperclip icon, select a text-based PDF resume
3. **Send a message**: Type "Summarize my resume" and press Enter
4. **Trigger skill gap analysis**: Type "What skills am I missing?" after uploading a resume
5. **Test rate limiting**: Send rapid requests with a PDF attached — you should see a 429 error toast after exceeding the limit

### Docker Network Testing

Verify inter-service connectivity:

```bash
# Check frontend can reach backend
docker exec resume-frontend curl -s http://backend:8001/health

# Check backend can reach Ollama
docker exec resume-backend curl -s http://ollama:11434/api/tags

# View all container logs
docker compose logs -f
```

---

## Limitations

### Known Issues

- **No conversation memory**: Each message is processed independently. The LLM cannot reference previous messages in the conversation.
- **No user authentication**: The application has no login system — anyone with access to the frontend URL can use it.
- **In-memory rate limiting**: The proxy's rate limiter stores request timestamps in process memory. Restarting the frontend container resets all limits.
- **Text-only PDFs**: Scanned documents or image-based PDFs cannot be processed by the client-side PDF.js extractor.
- **Hallucination risk**: The LLM may generate inaccurate skill gap recommendations if the database has insufficient tagged jobs or if the resume skill extraction fails.

### Performance

- **LLM latency**: Each chat request may take 5–60 seconds depending on the model, resume size, and number of job listings to analyze.
- **Batch processing**: Skill gap analysis processes jobs in batches. Large databases (>1000 tagged jobs) increase response time proportionally.
- **No caching**: Resume skill extraction and job tech stack fetching are recomputed on every request.

### Accuracy

- **Skill extraction**: The LLM-based skill extractor may miss subtle technologies or include false positives (e.g., extracting "leadership" as a skill).
- **Gap computation**: Only compares against jobs that have been tagged with a tech stack. Untagged jobs are invisible to the analysis.
- **Model quality**: Gemma 3:1B (used for intent classification) is a small model and may misclassify ambiguous messages.

### Missing Features

- No chat history persistence (in-browser only)
- No support for non-PDF file formats (DOCX, TXT)
- No real-time streaming of LLM responses
- No multi-language support
- No deployment beyond local Docker Compose

---

## Architecture Reflection

### Design Choices

**Microservices over monolith**: The frontend and backend are separated into distinct services communicating via HTTP. This mirrors real-world production architectures where UI and API teams work independently. The frontend serves as both a static file server and a reverse proxy, eliminating CORS complexity by ensuring the browser only ever talks to a single origin.

**Containerization with Docker Compose**: Each service (frontend, backend, Ollama) runs in its own container. This makes the entire application portable — a single `docker compose up` command deploys everything. The shared `app-net` bridge network enables service discovery by container name (e.g., `backend`, `ollama`), avoiding hardcoded IPs.

**MCP (Model Context Protocol) for database access**: The backend communicates with SQLite through `db_server.py`, a FastMCP server exposing SQL operations as tools. This decouples database logic from the AI pipeline and allows the same server to serve multiple consumers (skill gap analysis, tag data).

**Local LLM via Ollama**: Running Ollama in its own container provides free, unrestricted model inference without API costs or rate limits. Models are persisted in a named volume (`${HOME}/.ollama`), surviving container rebuilds.

### Trade-offs

**Simplicity vs. scalability**: The single-page HTML frontend (no React/Vue) keeps the project lightweight and avoids build steps. However, this means all JavaScript logic lives in one file, and state management is rudimentary. For a production app, a proper framework would be warranted.

**Statelessness vs. UX**: Each request is stateless — no session storage, no conversation history. This simplifies the backend (no database for chat logs) but limits the chatbot to single-turn interactions. A user can't ask follow-up questions like "Tell me more about Docker" in the same context.

**Gemini for responses, Ollama for classification**: The system uses Gemini (cloud) for high-quality chat responses and Gemma 3:1B (local) for lightweight intent classification. This hybrid approach balances quality and cost, but introduces a dependency on an internet connection and API key.

### Improvements

**Persistent chat history**: Storing conversations in a database (e.g., PostgreSQL) would enable multi-turn dialogue, user accounts, and session recovery. This is the most impactful single improvement.

**Better frontend framework**: Migrating to React or Vue would provide component-based architecture, reactive state management, and a smoother UX (streaming responses, typing indicators driven by SSE/WebSocket).

**Production deployment**: Currently designed for local Docker Compose. Deploying to a cloud provider (AWS ECS, Render, Fly.io) would require:
- Externalizing the SQLite database to a managed service
- Configuring a reverse proxy (nginx/Caddy) for TLS termination
- Adding authentication (JWT, OAuth)
- Using a managed LLM API or GPU-enabled containers

**Improved skill extraction**: Replacing the LLM-based resume parser with a rule-based NER pipeline (spaCy, Hugging Face) would eliminate hallucination risk and reduce latency.

**WebSocket for real-time responses**: Streaming the LLM's token-by-token output would eliminate the long wait time and show progress to the user.
