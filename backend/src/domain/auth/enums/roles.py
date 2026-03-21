from enum import StrEnum


class SystemRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


DEFAULT_ROLE = SystemRole.MEMBER
