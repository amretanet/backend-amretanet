import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .modules.database import ConnectToMongoDB, DisconnectMongoDB
from app.routes import main
from dotenv import load_dotenv

load_dotenv()

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


@app.get("/")
async def root():
    app_info = {"name": "Amreta Net RESTful API", "version": f"v{app_version}"}
    return app_info
