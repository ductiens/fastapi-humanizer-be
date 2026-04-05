from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import humanize, analysis, auth
from app.core.config import settings
from app.db.client import connect_to_mongo, close_mongo_connection

app = FastAPI(title="AI Humanizer Engine")

# allow_credentials=True is INCOMPATIBLE with allow_origins=["*"] per CORS spec.
# Browsers (especially in production) will block such requests.
# Use explicit origins OR disable credentials requirement.
cors_origins = settings.CORS_ORIGINS
if cors_origins == ["*"]:
    # Wildcard: disable credentials to stay spec-compliant
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Explicit origins: credentials are safe
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
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
