# FlyRank CRUD API

A simple To-Do REST API built with Python and FastAPI for the FlyRank Backend AI Engineer program.

The project started with in-memory CRUD operations, was upgraded to SQLite persistence, and was later migrated to PostgreSQL running in Docker.

## Features

- Create, read, update, and delete tasks
- Request validation and error handling
- RESTful API endpoints
- Swagger/OpenAPI documentation
- Persistent database storage
- PostgreSQL with Docker
- Environment-based database configuration

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- PostgreSQL
- Docker
- Psycopg
- python-dotenv

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Welcome message |
| GET | `/health` | Health check |
| GET | `/tasks` | Get all tasks |
| GET | `/tasks/{id}` | Get a task |
| POST | `/tasks` | Create a task |
| PUT | `/tasks/{id}` | Update a task |
| DELETE | `/tasks/{id}` | Delete a task |

## Database

The project originally used SQLite (`tasks.db`) for persistence.

For the database integration stage, SQLite was replaced with **PostgreSQL 16 running in Docker**.

The PostgreSQL database uses:

- Database: `tasks`
- User: `postgres`
- Port: `5433`
- Container: `taskdb`
- Volume: `taskdata`

The application reads the database connection string from `.env`:

```env
DATABASE_URL=postgres://postgres:qwerty@localhost:5433/tasks

The actual .env file is excluded from Git using .gitignore.

A safe template is provided in .env.example.

PostgreSQL Setup

PostgreSQL is started using Docker:

docker run --name taskdb `
  -e POSTGRES_PASSWORD=qwerty `
  -e POSTGRES_DB=tasks `
  -p 5433:5432 `
  -v taskdata:/var/lib/postgresql/data `
  -d postgres:16

The application automatically creates the tasks table when it starts.

Database Verification

The PostgreSQL database was verified using:

docker exec -it taskdb psql -U postgres -d tasks -c "\dt"

The tasks table was successfully created and verified with:

SELECT id, title, description, completed
FROM tasks
ORDER BY id;
CRUD Testing

The API was tested using PowerShell requests.

Verified operations include:

Creating a new task
Retrieving tasks
Updating an existing task
Deleting a task
Handling non-existent task IDs with 404 Not Found
Health check returning {"status": "ok"}

Example successful response:

{
  "id": 6,
  "title": "CRUD Test Task Updated",
  "description": "Testing PostgreSQL CRUD operations",
  "completed": true
}

A deleted task correctly returns:

{
  "detail": "Task not found"
}
Validation & Error Handling
Status	Meaning
200	Successful request
201	Task created
204	Task deleted
400	Invalid request body
404	Task not found
Running the API

Create and activate the virtual environment:

python -m venv venv
venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Configure .env using .env.example.

Start PostgreSQL:

docker start taskdb

Start FastAPI:

uvicorn main:app --reload

API:

http://127.0.0.1:8000

Swagger documentation:

http://127.0.0.1:8000/docs
Project History
Previous Stage

Implemented a FastAPI CRUD API with request validation, HTTP status codes, and SQLite persistence.

Database Integration Stage

Migrated the application from SQLite to PostgreSQL, containerized PostgreSQL using Docker, added environment-based configuration, and verified complete CRUD functionality against the PostgreSQL database.

Assignment

FlyRank Backend AI Engineering

Phase: Foundations

Previous Assignment: BE-02 — Connecting to the Database

Current Work: PostgreSQL & Docker Database Integration

The project demonstrates the progression from a basic CRUD API to a persistent PostgreSQL-backed REST API.