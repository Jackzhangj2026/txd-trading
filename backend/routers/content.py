"""Content management API routes — blog generation, media."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.blog_generator import BlogGenerator

router = APIRouter(prefix="/api/content", tags=["content"])


class GenerateResponse(BaseModel):
    success: bool
    title: str = ""
    slug: str = ""
    message: str = ""


@router.post("/generate-blog", response_model=GenerateResponse)
async def generate_blog():
    """Trigger a one-time blog post generation."""
    try:
        generator = BlogGenerator()
        post = await generator.run_daily()
        if post:
            return GenerateResponse(
                success=True,
                title=post["title"],
                slug=post["slug"],
                message=f"Blog post generated: {post['slug']}.html",
            )
        else:
            return GenerateResponse(
                success=True,
                message="All topics already published today. Try again tomorrow.",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
