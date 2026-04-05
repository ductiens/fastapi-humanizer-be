from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import humanize, analysis, auth
from app.db.client import connect_to_mongo, close_mongo_connection

app = FastAPI(title="AI Humanizer Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # NOTE: Restrict this in production!
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
async def root():
    return {"message": "Welcome to AI Humanizer API"}
