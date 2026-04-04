from __future__ import annotations

import os


os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
