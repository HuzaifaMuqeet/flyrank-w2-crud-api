from fastapi import FastAPI, HTTPException

app = FastAPI()


tasks = [
    {
        "id": 1,
        "title": "Learn FastAPI",
        "description": "Build my first CRUD API",
        "completed": False
    },
    {
        "id": 2,
        "title": "Test API endpoints",
        "description": "Test the CRUD operations",
        "completed": False
    }
]


@app.get("/")
def hello():
    return {"message": "Hello from my CRUD API!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task

    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )