from fastapi import FastAPI

from app.routers import api


app = FastAPI(
    title="PersonaLens MVP",
    description="Minimal, transparent, role-aware contextual lens for LLM responses",
    version="1.0.0",
)

# Include API router
app.include_router(api.router, tags=["PersonaLens"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
