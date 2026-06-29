"""FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(title="GeM Tender Automation API")


@app.get("/health")
def health():
    return {"status": "ok"}
