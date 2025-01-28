import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .modules.database import ConnectToMongoDB, DisconnectMongoDB
from app.routes import main
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

ASSET_DIR = Path("assets")
ASSET_DIR.mkdir(parents=True, exist_ok=True)

app_version = os.environ["API_VERSION"]

origins = os.environ["ORIGINS"].split(", ")

app = FastAPI(
    title="Amreta Net RESTful API",
    description="RESTful API for Amreta Net Apps",
    version=app_version,
)
app.add_event_handler("startup", ConnectToMongoDB)
app.add_event_handler("shutdown", DisconnectMongoDB)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(main.router)
app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="static")


@app.get("/")
async def root():
    app_info = {"name": "Amreta Net RESTful API", "version": f"v{app_version}"}
    return app_info
