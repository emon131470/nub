
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Studio API", version="0.1.0")

# Development/testing setup.
# Production-এ তোমার নির্দিষ্ট website origin ব্যবহার করবে।
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/")
def home():
    return {
        "message": "AI Studio API is running",
        "version": "0.1.0"
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "Python backend connected successfully"
    }

