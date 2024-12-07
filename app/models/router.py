from pydantic import BaseModel


# schemas
class RouterInsertData(BaseModel):
    name: str
    ip_address: str
    api_port: int
    username: str
    password: str
    status: int = 1
