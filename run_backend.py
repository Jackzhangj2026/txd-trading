"""Startup launcher — preload SQLAlchemy then start backend.

Uses `from X import Y` inside a sync function — the only pattern
that works on this Python 3.13 environment.
"""
import sys


def preload():
    """Import all sqlalchemy symbols inside a regular function."""
    print("[preload] Loading sqlalchemy...", flush=True)
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
    from sqlalchemy import select, func as sa_func, or_, and_, desc, text
    from sqlalchemy import String, Integer, Boolean, Float, Text, DateTime, ForeignKey
    from sqlalchemy import Index, JSON, Column, Enum
    print("[preload] All symbols cached in sys.modules", flush=True)


if __name__ == "__main__":
    preload()
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
