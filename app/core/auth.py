from fastapi import Header

async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    return {"uid": "dev-user"}
