from enum import Enum
from typing import Optional
from pydantic import BaseModel


# schemas
class ConfigurationType(str, Enum):
    GOOGLE_MAPS_API = "GOOGLE_MAPS_API"
    TELEGRAM_BOT = "TELEGRAM_BOT"
    EMAIL_BOT = "EMAIL_BOT"
    WHATSAPP_BOT = "WHATSAPP_BOT"


class MapsApiUpdateData(BaseModel):
    maps_api: str
    acs_api: str


class TelegramBotUpdateData(BaseModel):
    bot_token: str
    bot_username: str
    owner_id: str
    owner_username: str
    url_webhook: Optional[str] = None
    id_other: str
    id_psb: str
    id_notification: str
    id_payment: str
    id_webhook: str
    id_ticket: str


class EmailBotUpdateData(BaseModel):
    protocol: str
    host: str
    email: str
    password: str
    port: int
    name: str


class WhatsappBotUpdateData(BaseModel):
    bot_number: str
    admin_number: str
    url_gateway: str
    url_media: str
    url_server: str
    api_key: str
