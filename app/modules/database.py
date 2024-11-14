import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


class DataBase:
    client: AsyncIOMotorClient = None


db = DataBase()


async def ConnectToMongoDB():
    db.client = AsyncIOMotorClient(
        os.environ["AMRETA_DB_URI"], tls=True, tlsAllowInvalidCertificates=True
    )


async def DisconnectMongoDB():
    db.client.close()


async def GetBMDatabase() -> AsyncIOMotorClient:
    return db.client[os.environ["AMRETA_DB_NAME"]]
