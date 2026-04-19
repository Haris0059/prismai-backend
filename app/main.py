from contextlib import asynccontextmanager

from fastapi import FastAPI
import firebase_admin
from firebase_admin import credentials

import app.core.logging  # Setup structlog
from app.core.logging import RequestIDMiddleware
from app.core.settings import settings
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.dev_auth_bypass:
        if not settings.firebase_service_account_path:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_PATH must be set unless DEV_AUTH_BYPASS is true")
        cred = credentials.Certificate(settings.firebase_service_account_path)
        firebase_admin.initialize_app(cred)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)

app.include_router(chat_router)
app.include_router(conversations_router)
