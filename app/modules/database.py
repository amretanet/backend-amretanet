import os
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


class DataBase:
    client: AsyncIOMotorClient = None


db = DataBase()


async def ConnectToMongoDB():
     db.client = motor.motor_asyncio.AsyncIOMotorClient(
        os.environ["AMRETA_DB_URI"]
    )


async def DisconnectMongoDB():
    db.client.close()


async def GetAmretaDatabase() -> AsyncIOMotorClient:
    return db.client[os.environ["AMRETA_DB_NAME"]]
