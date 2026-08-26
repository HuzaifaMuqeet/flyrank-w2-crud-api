\# FlyRank CRUD API



A simple To-Do REST API built with Python and FastAPI for the FlyRank Backend AI Engineer Week 2 assignment.



\## Features



\- Create tasks

\- Read all tasks

\- Read an individual task

\- Update tasks

\- Delete tasks

\- Request validation

\- HTTP status code handling

\- Interactive Swagger/OpenAPI documentation

\- In-memory task storage



\## Tech Stack



\- Python 3.10+

\- FastAPI

\- Uvicorn

\- Pydantic



\## Installation



Clone the repository:



```bash

git clone https://github.com/HuzaifaMuqeet/flyrank-w2-crud-api.git

cd flyrank-w2-crud-api


curl.exe:
PS C:\\Users\\Admin\_01> curl.exe -i http://127.0.0.1:8000/tasks

HTTP/1.1 200 OK

date: Wed, 26 Aug 2026 21:03:21 GMT

server: uvicorn

content-length: 189

content-type: application/json



\[{"id":1,"title":"Learn FastAPI","description":"Build my first CRUD API","completed":false},{"id":2,"title":"Test API endpoints","description":"Test the CRUD operations","completed":false}]

