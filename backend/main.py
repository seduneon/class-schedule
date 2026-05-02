"""
FastAPI application entry point.

Start with:
    uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import results, solve, upload

app = FastAPI(
    title="Class Scheduling API",
    description="University class scheduling via Mixed Integer Linear Programming.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(solve.router)
app.include_router(results.router)


@app.get("/")
async def root():
    return {"message": "Class Scheduling API is running. Visit /docs for the Swagger UI."}
