from fastapi import FastAPI

import app.core.logging  # Setup structlog
from app.core.logging import RequestIDMiddleware
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router

app = FastAPI()

app.add_middleware(RequestIDMiddleware)

app.include_router(chat_router)
app.include_router(conversations_router)
