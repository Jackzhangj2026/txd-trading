"""AI-powered development email generator — creates personalized cold emails with random factory images."""

import json
import random
from pathlib import Path
from backend.agents import TradeAgent
from backend.config import settings

FACTORY_IMG_DIR = settings.factory_image_dir


def _get_random_images(count: int = 3) -> list[str]:
    """Pick random images from the factory image directory."""
    if not FACTORY_IMG_DIR.exists():
        return []
    all_images = sorted([
        f.name for f in FACTORY_IMG_DIR.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp") and not f.name.startswith(".")
    ])
    if not all_images:
        return []
    return random.sample(all_images, min(count, len(all_images)))


class EmailGenerator:
    """Generate personalized development emails using LLM, with random factory images."""

    def __init__(self):
        self.agent = TradeAgent(
            system_prompt="You are a professional B2B export sales copywriter for TXD CO., LTD, "
                          "a manufacturer of PP hollow sheets, corrugated plastic boxes, and packaging "
                          "solutions based in Xiamen, China. Write compelling, personalized sales emails."
        )

    async def generate_email(self, customer_name: str, company_name: str, country: str,
                              product_interest: str = "", template_style: str = "professional",
                              temperature: float = 0.7, include_images: bool = True) -> dict:
        """Generate a personalized development email with random product images."""
        product_context = f" They are interested in: {product_interest}." if product_interest else ""

        style_prompts = {
            "professional": "Write in a professional, formal B2B tone. Be direct but courteous.",
            "friendly": "Write in a warm, friendly tone. Build rapport first, then introduce offer.",
            "short": "Write a very short email (3-4 sentences). Get straight to the point.",
            "value_first": "Lead with value proposition and benefits. Mention specific pain points.",
        }
        style_text = style_prompts.get(template_style, style_prompts["professional"])

        # Pick random images
        image_filenames = []
        if include_images:
            image_filenames = _get_random_images(3)

        # Build image instruction
        image_instruction = ""
        if image_filenames:
            image_instruction = (
                "\n"
                "Also add a product showcase section in the email body using these placeholders:\n"
                "- {{image_1}} — insert product image 1 here\n"
                "- {{image_2}} — insert product image 2 here\n"
                "- {{image_3}} — insert product image 3 here\n"
                "Place them after the introduction, before the call-to-action. "
                "Add a short caption under each image describing the product shown. "
                "Use a clean table or div layout for the images."
            )

        prompt = f"""Generate a personalized cold outreach email for a potential buyer.

Recipient: {customer_name}
Company: {company_name}
Country: {country}{product_context}

Our company: TXD CO., LTD — a professional manufacturer and exporter of:
- PP hollow sheets (PP hollow board / corrugated plastic sheets)
- Custom PP/corrugated boxes
- ESD anti-static packaging sheets
- Plastic packaging solutions

{style_text}

Generate:
SUBJECT: An attention-grabbing email subject line (max 10 words). Personalize it for {company_name}.
BODY: The full email body in HTML format. Use <p> tags for paragraphs. Include:
- A personalized opening mentioning their company/country
- Brief introduction of TXD CO., LTD
- 2-3 key product benefits relevant to {product_interest or "packaging needs"}
- A clear call-to-action (ask for a quick call, quote request, or catalog download)
- Professional signature with company name
{image_instruction}

Make it sound HUMAN, not like a template. Vary the opening line. Don't sound robotic.

Respond ONLY with:
SUBJECT: <subject line>
BODY: <html body>
"""
        try:
            response = await self.agent.chat(prompt, temperature=temperature)
            subject = ""
            body = ""
            in_body = False
            body_lines = []

            for line in response.split("\n"):
                if line.startswith("SUBJECT:"):
                    subject = line.split(":", 1)[1].strip()
                elif line.startswith("BODY:"):
                    in_body = True
                    body_lines.append(line.split(":", 1)[1].strip())
                elif in_body:
                    body_lines.append(line)

            if in_body:
                body = "\n".join(body_lines)

            # Ensure image placeholders are present if images were selected
            if image_filenames:
                for i in range(1, len(image_filenames) + 1):
                    placeholder = f"{{image_{i}}}"
                    if placeholder not in body:
                        # Append to body if AI didn't place them
                        body += f"\n<p style='text-align:center;margin-top:20px;'>{placeholder}</p>"

            if not subject:
                subject = "Introduction from TXD CO., LTD - PP Hollow Board Supplier"
            if not body:
                body = f"<p>Dear {customer_name},</p><p>We are TXD CO., LTD, a leading manufacturer of PP hollow sheets and packaging solutions. We would love to discuss how we can support {company_name}'s packaging needs.</p>"

            return {
                "subject": subject,
                "body": body,
                "image_filenames": image_filenames,
            }
        except Exception as e:
            body_text = f"<p>Dear {customer_name},</p><p>We are TXD CO., LTD, a professional manufacturer of PP hollow sheets and custom packaging solutions based in Xiamen, China. We would be delighted to explore how our products could benefit {company_name}.</p><p>Looking forward to hearing from you.</p><p>Best regards,<br>TXD CO., LTD Sales Team</p>"
            if image_filenames:
                for i in range(1, len(image_filenames) + 1):
                    body_text += f"\n<p style='text-align:center;margin-top:20px;'>{{{{image_{i}}}}}</p>"
            return {
                "subject": "Introduction from TXD CO., LTD - Packaging Solutions",
                "body": body_text,
                "image_filenames": image_filenames,
            }
