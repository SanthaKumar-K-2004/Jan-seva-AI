"""
Jan-Seva AI — FastAPI Application Entry Point (API-Only)
No database dependencies. All data from live API calls.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils.rate_limiter import RateLimiter
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info(f"🚀 Jan-Seva AI starting in {settings.app_env} mode...")
    logger.info(f"🏗️ Architecture: API-Only (No Database)")
    logger.info(f"🤖 Groq: {len(settings.all_groq_keys)} key(s) {'✅' if settings.all_groq_keys else '❌'}")
    logger.info(f"💎 Gemini: {len(settings.all_google_keys)} key(s) {'✅' if settings.all_google_keys else '❌'}")
    logger.info(f"🧠 OpenAI: {len(settings.all_openai_keys)} key(s) {'✅' if settings.all_openai_keys else '❌'}")
    logger.info(f"🧠 NVIDIA: {'✅' if settings.nvidia_api_key else '❌'}")
    logger.info(f"🔍 Tavily: {'✅' if settings.tavily_api_key else '❌'}")
    logger.info(f"📰 NewsAPI: {'✅' if settings.news_api_key else '❌'}")
    logger.info(f"📚 Wikipedia: {'✅' if settings.wikipedia_access_token else '❌'}")
    logger.info(f"🦆 DuckDuckGo: ✅ (no key needed)")
    logger.info(f"🛡️ Strict verification: {'ON' if settings.strict_verified_mode else 'OFF'}")
    logger.info(f"🗂️ Research cache: {'ON' if settings.research_cache_enabled else 'OFF'}")

    yield

    logger.info("👋 Jan-Seva AI shutting down...")


app = FastAPI(
    title="Jan-Seva AI",
    description="Government Scheme Discovery & Eligibility Engine — Find the Unknown. Serve the Unserved. 100% API-driven.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Middleware Stack ---
app.add_middleware(RateLimiter, requests_per_minute=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global Error Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Something went wrong. Please try again later.",
            "path": str(request.url.path),
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": str(request.url.path)},
    )


# --- Health Check ---
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "healthy",
        "service": "Jan-Seva AI",
        "version": "2.0.0",
        "architecture": "api-only",
        "message": "Find the Unknown. Serve the Unserved. Charge Nothing.",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "architecture": "api-only (no database)",
        "services": {
            "groq_llm": len(settings.all_groq_keys) > 0,
            "gemini_llm": len(settings.all_google_keys) > 0,
            "openai_llm": len(settings.all_openai_keys) > 0,
            "nvidia_qwen": bool(settings.nvidia_api_key),
            "tavily_search": bool(settings.tavily_api_key),
            "news_api": bool(settings.news_api_key),
            "wikipedia": bool(settings.wikipedia_access_token),
            "duckduckgo": True,
            "whatsapp": bool(settings.whatsapp_access_token),
            "research_cache": bool(settings.research_cache_enabled),
            "strict_source_verification": bool(settings.strict_verified_mode),
        },
    }


# --- Register Routers ---
from app.api import chat, schemes, eligibility, users, admin, whatsapp, research, analytics

app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(schemes.router, prefix="/api/v1/schemes", tags=["Schemes"])
app.include_router(eligibility.router, prefix="/api/v1/eligibility", tags=["Eligibility"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(whatsapp.router, prefix="/api/v1/webhook", tags=["WhatsApp"])
app.include_router(research.router, prefix="/api/v1/research", tags=["Research"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
