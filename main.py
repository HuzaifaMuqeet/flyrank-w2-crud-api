from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def hello():
    return {"message": "Hello from my CRUD API!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}