import os
import sys
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("OPENROUTER_API_KEY"):
    # when packaged as .exe, look for .env beside the executable
    load_dotenv(Path(sys.executable).parent / ".env")

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise SystemExit(
        "\n[PDF Study Buddy] OPENROUTER_API_KEY not found!\n"
        "Create a file named exactly '.env' in the project folder containing:\n"
        "OPENROUTER_API_KEY=sk-or-v1-your-actual-key\n"
    )

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

MODEL = "google/gemma-4-26b-a4b-it:free"

SYSTEM_PROMPT = (
    "You are a friendly study buddy. Explain the target word in simple "
    "Roman Hinglish (conversational Hindi mixed with English, written in Latin script). "
    "Keep it to 2-4 short sentences. Use the context to pick the exact right meaning. "
    "Do not use jargon. Do not say 'Here is the explanation'. Just explain it directly."
)


async def stream_explanation(word: str, context: str):
    prompt = f"Context paragraph: {context}\n\nTarget word to explain: {word}"
    stream = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def stream_summary(page_text: str):
    prompt = (
        "Page text:\n" + page_text +
        "\n\nSummarize this page in simple Roman Hinglish (3-5 short sentences). "
        "Main idea + key points batao, study-buddy style."
    )
    stream = await client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def get_image_query(word: str, context: str) -> str:
    """Ask the AI for ONE short, relevant image-search query (English)."""
    prompt = (
        f"Context: {context}\n"
        f"Word: {word}\n\n"
        "Write ONE short English phrase (2-6 words) naming the exact concept or object, "
        "like a Wikipedia article title (e.g. 'Computer terminal', 'Photosynthesis', "
        "'RAM memory module'). Reply with ONLY the phrase, nothing else."
    )
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()
        lines = [ln.strip().strip('"').strip("'") for ln in raw.splitlines() if ln.strip()]
        q = lines[0] if lines else ""
        if q and len(q) <= 60:
            return q
    except Exception as ex:
        print(f"[visuals] query generation failed: {ex}")
    return word  # fallback: plain word