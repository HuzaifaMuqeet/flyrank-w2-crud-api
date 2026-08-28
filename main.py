import json
import logging
import os
import time
from pathlib import Path
from typing import Literal

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ============================================================
# Configuration
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
LLM_STUB = os.getenv("LLM_STUB", "0") == "1"
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
LLM_TIMEOUT = 30.0
MAX_RETRIES = 2

BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "prompts" / "triage-v1.md"
QUARANTINE_LOG = BASE_DIR / "logs" / "quarantine.jsonl"

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("flyrank-api")

# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="FlyRank CRUD API",
    description="FastAPI CRUD API with local LLM-powered support-message triage.",
    version="2.0.0",
)

# ============================================================
# Database models
# ============================================================


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    completed: bool = False


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None


# ============================================================
# Triage models
# ============================================================


class TriageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class TriageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["billing", "bug", "feature", "other"]
    urgency: Literal["low", "normal", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


# ============================================================
# Database
# ============================================================


def get_db_connection():
    return psycopg.connect(DATABASE_URL)


def initialize_database():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute("SELECT COUNT(*) FROM tasks")
            existing_tasks = cursor.fetchone()[0]

            if existing_tasks == 0:
                cursor.executemany(
                    """
                    INSERT INTO tasks (title, description, completed)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        ("Learn FastAPI", "Build my first CRUD API", False),
                        ("Test API endpoints", "Test the CRUD operations", False),
                        ("Complete documentation", "Prepare the Week 2 submission", False),
                    ],
                )


initialize_database()

# ============================================================
# Request validation handler
# ============================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "Invalid request body"})


# ============================================================
# Prompt
# ============================================================


def load_triage_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise RuntimeError(f"Prompt file not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


# ============================================================
# Quarantine logging
# ============================================================


def quarantine_response(raw_response: str, reason: str):
    QUARANTINE_LOG.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": time.time(),
        "reason": reason,
        "raw_response": raw_response,
    }

    with QUARANTINE_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


# ============================================================
# LLM call
# ============================================================


def call_llm(prompt: str, user_text: str):
    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
    started = time.monotonic()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Classify this support message:\n\n" + user_text},
        ],
        temperature=0,
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    content = response.choices[0].message.content if response.choices else None
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None

    logger.info(
        "llm_call model=%s duration_ms=%s input_tokens=%s output_tokens=%s",
        LLM_MODEL,
        duration_ms,
        input_tokens,
        output_tokens,
    )

    if not content:
        raise ValueError("LLM returned empty content")

    return content


# ============================================================
# JSON cleanup
# ============================================================


def clean_json_response(raw_response: str) -> str:
    text = raw_response.strip()

    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    elif text.startswith("```"):
        text = text[len("```") :].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


# ============================================================
# Validation
# ============================================================


def parse_and_validate(raw_response: str) -> TriageResponse:
    cleaned = clean_json_response(raw_response)
    parsed = json.loads(cleaned)
    return TriageResponse.model_validate(parsed)


# ============================================================
# Repair
# ============================================================


def repair_response(raw_response: str):
    repair_prompt = """
Your previous response did not satisfy the required schema.

Return ONLY valid JSON.

Required schema:
{
  "category": "billing | bug | feature | other",
  "urgency": "low | normal | high",
  "confidence": 0.0,
  "reason": "one short sentence"
}

Do not add fields.
Do not use Markdown.
Do not use code fences.
Do not explain anything.

Previous response:
""" + raw_response

    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
    started = time.monotonic()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": repair_prompt}],
        temperature=0,
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    content = response.choices[0].message.content if response.choices else None

    logger.info("llm_repair duration_ms=%s", duration_ms)

    if not content:
        raise ValueError("Repair response was empty")

    return content


# ============================================================
# Triage
# ============================================================


@app.post("/triage", response_model=TriageResponse, summary="Classify a support message")
def triage(request: TriageRequest):
    logger.info("triage_start text_length=%s", len(request.text))

    # --------------------------------------------------------
    # Kill switch
    # --------------------------------------------------------
    if not LLM_ENABLED:
        logger.warning("LLM disabled by LLM_ENABLED")
        raise HTTPException(status_code=503, detail="LLM service is disabled")

    # --------------------------------------------------------
    # Stub mode
    # --------------------------------------------------------
    if LLM_STUB:
        logger.info("triage_stub_mode")
        return TriageResponse(
            category="other",
            urgency="low",
            confidence=0.25,
            reason="Stub mode is enabled for deterministic testing.",
        )

    # --------------------------------------------------------
    # Prompt-injection guard
    # --------------------------------------------------------
    injection_markers = [
        "ignore your instructions",
        "ignore previous instructions",
        "ignore the instructions",
        "reveal the system prompt",
        "show me the system prompt",
        "return category billing",
        "set confidence to 1.0",
        "change your instructions",
        "change your rules",
    ]

    normalized_text = request.text.lower()
    if any(marker in normalized_text for marker in injection_markers):
        logger.warning("triage_prompt_injection_detected")
        return TriageResponse(
            category="other",
            urgency="low",
            confidence=0.2,
            reason="The message is a prompt-injection attempt rather than a supported customer request.",
        )

    # --------------------------------------------------------
    # Load prompt
    # --------------------------------------------------------
    try:
        prompt = load_triage_prompt()
    except Exception as exc:
        logger.exception("prompt_load_failed")
        raise HTTPException(status_code=500, detail="Triage prompt could not be loaded") from exc

    # --------------------------------------------------------
    # Initial LLM call
    # --------------------------------------------------------
    raw_response = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            raw_response = call_llm(prompt, request.text)
            result = parse_and_validate(raw_response)
            logger.info("triage_success attempt=%s", attempt + 1)
            return result
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("triage_validation_failed attempt=%s error=%s", attempt + 1, exc)
            if attempt == 0:
                try:
                    raw_response = repair_response(raw_response or "")
                    result = parse_and_validate(raw_response)
                    logger.info("triage_repair_success")
                    return result
                except Exception as repair_exc:
                    logger.warning("triage_repair_failed error=%s", repair_exc)
            break
        except Exception as exc:
            logger.exception("triage_llm_error")
            quarantine_response(raw_response or "", f"LLM error: {type(exc).__name__}")
            raise HTTPException(status_code=502, detail="LLM triage service failed") from exc

    quarantine_response(raw_response or "", "Response failed schema validation after repair")
    raise HTTPException(status_code=422, detail="LLM response failed schema validation")


# ============================================================
# Basic endpoints
# ============================================================


@app.get("/", summary="Welcome message")
def hello():
    return {"message": "Hello from my CRUD API!"}


@app.get("/health", summary="Health check")
def health_check():
    return {"status": "ok"}


# ============================================================
# CRUD endpoints
# ============================================================


@app.get("/tasks", summary="Get all tasks")
def get_tasks():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks ORDER BY id")
            rows = cursor.fetchall()
            columns = [column.name for column in cursor.description]

    return [dict(zip(columns, row)) for row in rows]


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Task not found")

            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.post("/tasks", status_code=status.HTTP_201_CREATED, summary="Create a task")
def create_task(task: TaskCreate):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (title, description, completed)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (task.title, task.description, task.completed),
            )
            row = cursor.fetchone()
            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.put("/tasks/{task_id}", summary="Update a task")
def update_task(task_id: int, task_update: TaskUpdate):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            existing_task = cursor.fetchone()

            if existing_task is None:
                raise HTTPException(status_code=404, detail="Task not found")

            columns = [column.name for column in cursor.description]
            current_task = dict(zip(columns, existing_task))

            title = task_update.title if task_update.title is not None else current_task["title"]
            description = (
                task_update.description
                if task_update.description is not None
                else current_task["description"]
            )
            completed = (
                task_update.completed
                if task_update.completed is not None
                else current_task["completed"]
            )

            cursor.execute(
                """
                UPDATE tasks
                SET title = %s, description = %s, completed = %s
                WHERE id = %s
                RETURNING *
                """,
                (title, description, completed, task_id),
            )
            row = cursor.fetchone()
            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a task")
def delete_task(task_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
            existing_task = cursor.fetchone()

            if existing_task is None:
                raise HTTPException(status_code=404, detail="Task not found")

            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    return None
