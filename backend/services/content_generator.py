"""Content generator — LLM-powered social media content creation."""
# Stub — will be fully implemented in Task 2

class ContentGenerator:
    async def generate_for_platform(self, topic: str, platform: str) -> dict:
        return {"title": topic, "body": f"Content for {platform} about: {topic}", "media_urls": []}
