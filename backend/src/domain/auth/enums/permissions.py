from enum import StrEnum


class SystemPermission(StrEnum):
    USERS_READ = "users.read"
    USERS_BAN = "users.ban"
    USERS_MANAGE_ROLES = "users.manage_roles"


ADMIN_PERMISSIONS: tuple[SystemPermission, ...] = (
    SystemPermission.USERS_READ,
    SystemPermission.USERS_BAN,
    SystemPermission.USERS_MANAGE_ROLES,
)
