"""Image processing service — thumbnail generation, description via LLM."""

import os
from pathlib import Path
from backend.agents import TradeAgent

PRODUCT_IMAGE_DIRS = [
    Path("images/products/sheets"),
    Path("images/products/boxes"),
]


class ImageProcessor:
    """Scan, thumbnail, and describe product images."""

    def __init__(self):
        self.agent = TradeAgent(system_prompt="You are a product image analyst for an e-commerce packaging company.")

    def scan_new_images(self) -> list[dict]:
        """Find new images not yet processed. Returns list of {path, dir, filename}."""
        new_images = []
        for img_dir in PRODUCT_IMAGE_DIRS:
            if not img_dir.exists():
                continue
            for f in img_dir.iterdir():
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    thumb_dir = img_dir / "thumbs"
                    thumb_path = thumb_dir / f.name
                    if not thumb_path.exists():
                        new_images.append({
                            "path": str(f),
                            "dir": str(img_dir),
                            "filename": f.name,
                        })
        return new_images

    async def describe_image(self, image_path: str) -> str:
        """Generate alt-text and description for a product image using LLM (based on filename context)."""
        filename = Path(image_path).stem
        # Clean up filename to make a readable description
        name_parts = filename.replace("_", " ").replace("-", " ").split()
        name_parts = [p for p in name_parts if not any(c.isdigit() for c in p) or len(p) < 3]
        context = " ".join(name_parts[:8]) if name_parts else "product image"

        prompt = f"""Generate a brief product image description (max 100 chars) for: {context}
The image is from a PP hollow board / corrugated plastic box manufacturer.
Output only the description text, no prefix."""
        try:
            return await self.agent.chat(prompt, temperature=0.3)
        except Exception:
            return f"Product image: {filename}"
