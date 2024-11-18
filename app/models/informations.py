from enum import Enum


# schemas
class InformationType(str, Enum):
    INFO_ANNOUNCEMENT = "INFO_ANNOUNCEMENT"
    INFO_RULES = "INFO_RULES"
    INFO_PRIVACY = "INFO_PRIVACY"
    INFO_ABOUT = "INFO_ABOUT"
