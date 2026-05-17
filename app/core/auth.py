from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin.auth
from app.core.settings import settings

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Security(security)) -> dict:
    if settings.dev_auth_bypass:
        return {"uid": "dev-user", "email": "dev@example.com"}

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        return {"uid": decoded["uid"], "email": decoded.get("email")}
    except (
        ValueError, 
        firebase_admin.auth.InvalidIdTokenError, 
        firebase_admin.auth.ExpiredIdTokenError, 
        firebase_admin.auth.RevokedIdTokenError,
        firebase_admin.auth.UserDisabledError,
        firebase_admin.auth.CertificateFetchError
    ) as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
