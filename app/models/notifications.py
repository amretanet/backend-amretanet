from enum import Enum


# schemas
class NotificationTypeData(str, Enum):
    TICKET = "TICKET"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    PAYMENT_CONFIRM = "PAYMENT_CONFIRM"
