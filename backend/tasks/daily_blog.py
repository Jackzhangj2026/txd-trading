"""Daily blog post generation task."""

from backend.services.blog_generator import BlogGenerator


async def scheduled_blog_task():
    """Generate a daily SEO blog post."""
    generator = BlogGenerator()
    post = await generator.run_daily()
    if post:
        print(f"Blog post generated: {post['slug']}.html")
    else:
        print("Blog post skipped — already published today.")
