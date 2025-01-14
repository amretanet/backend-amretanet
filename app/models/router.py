from pydantic import BaseModel

# responses
RouterProjections = {
    "name": 1,
    "ip_address": 1,
    "api_port": 1,
    "username": 1,
    "password": 1,
    "status": 1,
}


# schemas
class RouterInsertData(BaseModel):
    name: str
    ip_address: str
    api_port: int
    username: str
    password: str
    status: int = 1
