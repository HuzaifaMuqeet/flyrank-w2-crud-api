import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


app = FastAPI(
    title="FlyRank CRUD API",
    description="A simple To-Do REST API built with FastAPI for the FlyRank Backend AI Engineer Week 2 assignment.",
    version="1.0.0"
)


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    completed: bool = False


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None


# -----------------------------
# Database setup
# -----------------------------

def get_db_connection():
    return psycopg.connect(DATABASE_URL)


def initialize_database():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("SELECT COUNT(*) FROM tasks")
            existing_tasks = cursor.fetchone()[0]

            if existing_tasks == 0:
                cursor.executemany(
                    """
                    INSERT INTO tasks
                        (title, description, completed)
                    VALUES
                        (%s, %s, %s)
                    """,
                    [
                        (
                            "Learn FastAPI",
                            "Build my first CRUD API",
                            False
                        ),
                        (
                            "Test API endpoints",
                            "Test the CRUD operations",
                            False
                        ),
                        (
                            "Complete documentation",
                            "Prepare the Week 2 submission",
                            False
                        )
                    ]
                )


initialize_database()


# -----------------------------
# Validation
# -----------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Invalid request body"
        }
    )


# -----------------------------
# Basic endpoints
# -----------------------------

@app.get("/", summary="Welcome message")
def hello():
    return {"message": "Hello from my CRUD API!"}


@app.get("/health", summary="Health check")
def health_check():
    return {"status": "ok"}


# -----------------------------
# CRUD endpoints
# -----------------------------

@app.get("/tasks", summary="Get all tasks")
def get_tasks():
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tasks ORDER BY id"
            )

            rows = cursor.fetchall()

            columns = [column.name for column in cursor.description]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tasks WHERE id = %s",
                (task_id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Task not found"
                )

            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
    summary="Create a task"
)
def create_task(task: TaskCreate):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO tasks
                    (title, description, completed)
                VALUES
                    (%s, %s, %s)
                RETURNING *
                """,
                (
                    task.title,
                    task.description,
                    task.completed
                )
            )

            row = cursor.fetchone()
            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.put(
    "/tasks/{task_id}",
    summary="Update a task"
)
def update_task(task_id: int, task_update: TaskUpdate):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT * FROM tasks WHERE id = %s",
                (task_id,)
            )

            existing_task = cursor.fetchone()

            if existing_task is None:
                raise HTTPException(
                    status_code=404,
                    detail="Task not found"
                )

            columns = [column.name for column in cursor.description]
            current_task = dict(zip(columns, existing_task))

            title = (
                task_update.title
                if task_update.title is not None
                else current_task["title"]
            )

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
                SET
                    title = %s,
                    description = %s,
                    completed = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    title,
                    description,
                    completed,
                    task_id
                )
            )

            row = cursor.fetchone()
            columns = [column.name for column in cursor.description]

    return dict(zip(columns, row))


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task"
)
def delete_task(task_id: int):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id FROM tasks WHERE id = %s",
                (task_id,)
            )

            existing_task = cursor.fetchone()

            if existing_task is None:
                raise HTTPException(
                    status_code=404,
                    detail="Task not found"
                )

            cursor.execute(
                "DELETE FROM tasks WHERE id = %s",
                (task_id,)
            )

    return