import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the router from the new api module
from src.api import research, threads
from src.database import create_db_and_tables

# Create the database tables on startup
create_db_and_tables()


app = FastAPI(
    title="Project Ronin API",
    version="1.0.0",
    description="Asynchronous orchestration backend for Deep Research Agents"
)

# Standard CORS policy to allow your future frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Explicitly allow your Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],                      # Allow GET, POST, OPTIONS, etc.
    allow_headers=["*"],                      # Allow all headers
)

# Register the research endpoints
app.include_router(research.router, prefix="/api/v1")
app.include_router(threads.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ronin-backend"}

if __name__ == "__main__":
    # Allows you to run this locally outside of Docker for quick testing
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)