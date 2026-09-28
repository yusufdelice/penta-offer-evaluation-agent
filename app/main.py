from fastapi import FastAPI
from app.config import settings
from app.api.routes import router as evaluate_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Yapay Zekâ Destekli Teklif Ön Değerlendirme Agent API"
)

app.include_router(evaluate_router)


@app.get("/")
def read_root():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.VERSION
    }