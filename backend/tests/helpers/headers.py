def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
