import os
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


class DataBase:
    client: AsyncIOMotorClient = None


db = DataBase()
db_local = DataBase()


async def ConnectToMongoDB():
    db.client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["AMRETA_DB_URI"])
    db_local.client = motor.motor_asyncio.AsyncIOMotorClient(
        "mongodb://localhost:27017/"
    )


async def DisconnectMongoDB():
    db.client.close()
    db_local.client.close()


async def GetAmretaDatabase() -> AsyncIOMotorClient:
    return db.client[os.environ["AMRETA_DB_NAME"]]


async def GetLocalhostDatabase() -> AsyncIOMotorClient:
    return db_local.client[os.environ["AMRETA_DB_NAME"]]
