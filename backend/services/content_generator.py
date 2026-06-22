"""Content generator — LLM-powered social media content for 10 platforms."""

from backend.agents import TradeAgent


class ContentGenerator:
    """Generate platform-optimized content from a core topic."""

    def __init__(self):
        self.agent = TradeAgent(system_prompt="You are a social media content strategist for a B2B packaging materials company specializing in PP hollow boards.")

    async def generate_for_platform(self, topic: str, platform: str) -> dict:
        """Generate content for a specific platform. Dispatches to platform-specific method."""
        method_map = {
            "linkedin": self._linkedin_post,
            "twitter": self._twitter_thread,
            "youtube": self._youtube_script,
            "pinterest": self._pinterest_pin,
            "tiktok": self._tiktok_script,
            "facebook": self._facebook_post,
            "red": self._red_note,
            "douyin": self._douyin_script,
            "wechat_article": self._wechat_article,
            "wechat_moment": self._wechat_moment,
        }
        method = method_map.get(platform)
        if not method:
            return {"title": topic, "body": f"Content for {platform}: {topic}", "media_urls": []}
        return await method(topic)

    async def _linkedin_post(self, topic: str) -> dict:
        prompt = f"""Write a professional LinkedIn post about: {topic}

Company: TXD CO., LTD Trading — PP hollow sheet and corrugated plastic box manufacturer.

Requirements:
- Professional B2B tone
- 150-250 words
- Include 3-5 relevant hashtags
- End with a question to drive engagement

Respond in format:
TITLE: <post title/hook>
BODY: <full post text with line breaks>"""
        return await self._call_and_parse(prompt, topic, "linkedin")

    async def _twitter_thread(self, topic: str) -> dict:
        prompt = f"""Write a Twitter/X thread about: {topic}

Requirements:
- 4-6 tweets in the thread
- Each tweet under 280 characters
- Engaging hook in first tweet
- Include relevant hashtags in last tweet
- B2B/professional tone

Respond in format:
TITLE: <thread title>
BODY: <tweet 1>\n\n<tweet 2>\n\n<tweet 3>..."""
        return await self._call_and_parse(prompt, topic, "twitter")

    async def _youtube_script(self, topic: str) -> dict:
        prompt = f"""Write a YouTube video script about: {topic}

Requirements:
- 3-5 minute video length
- Hook (0:00-0:30)
- Main content (0:30-3:00)
- Call to action (3:00-3:30)
- Professional, educational tone

Respond in format:
TITLE: <video title>
BODY: <full script with timestamps>"""
        return await self._call_and_parse(prompt, topic, "youtube")

    async def _pinterest_pin(self, topic: str) -> dict:
        prompt = f"""Write a Pinterest pin description about: {topic}

Requirements:
- 1-2 sentence description
- 3-5 relevant keywords
- Call to action
- 5 relevant hashtags

Respond in format:
TITLE: <pin title>
BODY: <description with hashtags>"""
        return await self._call_and_parse(prompt, topic, "pinterest")

    async def _tiktok_script(self, topic: str) -> dict:
        prompt = f"""Write a TikTok short video script about: {topic}

Requirements:
- 30-60 seconds
- Hook (first 3 seconds)
- Fast-paced, engaging
- Text overlay suggestions in [brackets]
- Call to action at end

Respond in format:
TITLE: <video title>
BODY: <script with timings and on-screen text suggestions>"""
        return await self._call_and_parse(prompt, topic, "tiktok")

    async def _facebook_post(self, topic: str) -> dict:
        prompt = f"""Write a Facebook post about: {topic}

Requirements:
- Friendly, conversational tone
- 100-200 words
- Include 3 hashtags
- Ask for comments/shares

Respond in format:
TITLE: <post title>
BODY: <post content>"""
        return await self._call_and_parse(prompt, topic, "facebook")

    async def _red_note(self, topic: str) -> dict:
        """Generate a RED note — clean text, no image placeholders (images auto-uploaded)."""
        prompt = f"""Write a Xiaohongshu (RED) note in ENGLISH for international audience.

Topic: {topic}
Company: TXD CO., LTD — PP hollow board manufacturer in Xiamen, China.

CRITICAL RULES:
- Title MUST be 20 characters or less (RED limit)
- DO NOT include any image placeholders like {{{{image_1}}}} — images will be added automatically
- DO NOT include photo references like "photo 1", "Image 1", "▲ see photo" etc.
- Output as clean HTML: use <p> for paragraphs, <b> for emphasis
- Start with an engaging <h3> title line
- 150-300 words, friendly authentic sharing tone (not sales pitch)
- Include 3-5 emoji throughout
- End with a question to engage readers
- Finish with <p> hashtags: #PPhollowBoard #SustainablePackaging #FactoryDirect etc.

Respond in format:
TITLE: <title under 20 chars>
BODY: <h3>...</h3>
<p>...</p>
<p>...</p>"""
        return await self._call_and_parse(prompt, topic, "red")

    async def _douyin_script(self, topic: str) -> dict:
        """Generate a 抖音 Douyin video script (Chinese)."""
        prompt = f"""Write a 抖音 短视频脚本 about: {topic}

Requirements:
- 中文 (Chinese only)
- 15-30秒视频脚本
- 开头3秒吸引眼球
- 展示工厂实力/产品优势
- 结尾引导互动

Respond in format:
TITLE: <视频标题>
BODY: <脚本内容，包含画面描述和口播文案>"""
        return await self._call_and_parse(prompt, topic, "douyin")

    async def _wechat_article(self, topic: str) -> dict:
        """Generate a 微信 公众号 article (Chinese)."""
        prompt = f"""Write a 微信公众号 article about: {topic}

Requirements:
- 中文 (Chinese only)
- 800-1200字完整文章
- 专业但易读的风格
- 3-4个小标题分段
- 结尾包含公司介绍和联系方式

Respond in format:
TITLE: <文章标题>
BODY: <完整文章内容>"""
        return await self._call_and_parse(prompt, topic, "wechat_article")

    async def _wechat_moment(self, topic: str) -> dict:
        """Generate a 微信朋友圈 post (Chinese)."""
        prompt = f"""Write a 微信朋友圈 post about: {topic}

Requirements:
- 中文 (Chinese only)
- 100-200字
- 轻松友好风格
- 1-2个emoji
- 适合朋友圈分享

Respond in format:
TITLE: <标题>
BODY: <朋友圈文案>"""
        return await self._call_and_parse(prompt, topic, "wechat_moment")

    async def generate_all(self, topic: str) -> dict:
        """Generate content for all 10 platforms at once."""
        platforms = [
            "linkedin", "twitter", "youtube", "pinterest", "tiktok",
            "facebook", "red", "douyin", "wechat_article", "wechat_moment",
        ]
        results = {}
        for platform in platforms:
            result = await self.generate_for_platform(topic, platform)
            results[platform] = result
        return results

    async def _call_and_parse(self, prompt: str, topic: str, platform: str) -> dict:
        """Call LLM and parse the structured response."""
        try:
            response = await self.agent.chat(prompt, temperature=0.7)
            lines = response.strip().split("\n")
            title = topic
            body_lines = []
            in_body = False

            for line in lines:
                if line.startswith("TITLE:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("BODY:"):
                    in_body = True
                    body_lines.append(line.split(":", 1)[1].strip())
                elif in_body:
                    body_lines.append(line)

            body = "\n".join(body_lines) if body_lines else response
            return {"title": title or topic, "body": body, "media_urls": []}
        except Exception as e:
            return {"title": topic, "body": f"[{platform}] Content about: {topic}", "media_urls": []}
