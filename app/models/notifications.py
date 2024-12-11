from enum import Enum


# schemas
class NotificationTypeData(str, Enum):
    TICKET = "TICKET"
    PAYMENT_CONFIRM = "PAYMENT_CONFIRM"
