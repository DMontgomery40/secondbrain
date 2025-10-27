from pathlib import Path

from src.second_brain.config import Config
from src.second_brain.ocr.openai_ocr import OpenAIOCR
from src.second_brain.ocr.deepseek_ocr import DeepSeekOCR


def main(image_path: str) -> None:
    cfg = Config()
    openai = OpenAIOCR(cfg)
    deepseek = DeepSeekOCR(cfg)

    p = Path(image_path)
    frame_id = "test-frame"

    import asyncio

    async def run():
        print("Testing OpenAI OCR...")
        r1 = await openai.extract_text(p, frame_id)
        print(f"OpenAI blocks: {len(r1)}, text length: {len(r1[0]['text']) if r1 else 0}")

        print("\nTesting DeepSeek OCR...")
        r2 = await deepseek.extract_text(p, frame_id)
        print(f"DeepSeek blocks: {len(r2)}, text length: {len(r2[0]['text']) if r2 else 0}")

        common = set((r1[0]["text"] if r1 else "").split()) & set((r2[0]["text"] if r2 else "").split())
        base = set((r1[0]["text"] if r1 else "").split()) or {""}
        similarity = len(common) / len(base)
        print(f"\nText similarity: {similarity:.2%}")

    asyncio.run(run())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_engines.py /path/to/image.png")
        sys.exit(1)
    main(sys.argv[1])

