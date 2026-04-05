from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import humanize, analysis, auth
from app.core.config import settings
from app.db.client import connect_to_mongo, close_mongo_connection

app = FastAPI(title="AI Humanizer Engine")

# Explicitly define origins for production to avoid issues with allow_credentials=True
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://react-humanizer-fe.vercel.app",
    "*" # Keep * for now but explicit ones help with credentials
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

app.include_router(humanize.router)
app.include_router(analysis.router)
app.include_router(auth.router)

@app.get("/")
@app.head("/") # Support Render health check
async def root():
    return {"message": "Welcome to AI Humanizer API"}
