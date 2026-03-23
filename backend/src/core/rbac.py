from uuid import UUID

PERMISSIONS_CACHE_TTL_SECONDS = 900 # 15 minutes
ROLES_CACHE_TTL_SECONDS = 900 # 15 minutes


def permissions_cache_key(user_id: UUID | str, version: int) -> str:
    return f"auth:perm:{user_id}:v{version}"

def roles_cache_key(user_id: UUID | str, version: int) -> str:
    return f"auth:roles:{user_id}:v{version}"
 
 
GLOBAL_ROLE_IMPLICATIONS = {
    "admin": {"uploader"},
    "uploader": set(),
}

TEAM_ROLE_IMPLICATIONS = {
    "owner": {"admin"},
    "admin": set(),
}
