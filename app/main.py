import logging
import uvicorn
from fastapi import FastAPI
from .routers import slack

# Minimal FastAPI setup
app = FastAPI()

app.include_router(slack.router, prefix="/slack", tags=["slack"])

logging.basicConfig(level=logging.INFO)

@app.get("/")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
