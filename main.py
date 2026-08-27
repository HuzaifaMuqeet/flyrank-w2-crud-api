from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3


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

DATABASE = "tasks.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            completed INTEGER NOT NULL DEFAULT 0
        )
    """)

    existing_tasks = connection.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    if existing_tasks == 0:
        connection.executemany(
            """
            INSERT INTO tasks (id, title, description, completed)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "Learn FastAPI",
                    "Build my first CRUD API",
                    0
                ),
                (
                    2,
                    "Test API endpoints",
                    "Test the CRUD operations",
                    0
                ),
                (
                    3,
                    "Complete documentation",
                    "Prepare the Week 2 submission",
                    0
                )
            ]
        )

    connection.commit()
    connection.close()


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
    connection = get_db_connection()

    rows = connection.execute(
        "SELECT * FROM tasks"
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


@app.get("/tasks/{task_id}", summary="Get a task by ID")
def get_task(task_id: int):
    connection = get_db_connection()

    row = connection.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return dict(row)


@app.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
    summary="Create a task"
)
def create_task(task: TaskCreate):
    connection = get_db_connection()

    cursor = connection.execute(
        """
        INSERT INTO tasks (title, description, completed)
        VALUES (?, ?, ?)
        """,
        (
            task.title,
            task.description,
            int(task.completed)
        )
    )

    task_id = cursor.lastrowid

    connection.commit()

    row = connection.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    connection.close()

    return dict(row)


@app.put(
    "/tasks/{task_id}",
    summary="Update a task"
)
def update_task(task_id: int, task_update: TaskUpdate):
    connection = get_db_connection()

    existing_task = connection.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if existing_task is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    current_task = dict(existing_task)

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

    connection.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, completed = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            int(completed),
            task_id
        )
    )

    connection.commit()

    updated_task = connection.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    connection.close()

    return dict(updated_task)


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task"
)
def delete_task(task_id: int):
    connection = get_db_connection()

    existing_task = connection.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if existing_task is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    connection.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    connection.commit()
    connection.close()

    return