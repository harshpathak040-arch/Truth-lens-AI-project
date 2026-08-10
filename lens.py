"""
TruthLens AI — lens.py
============================================================
Backend for the standalone lens.html page.

Serves the HTML file directly (it's fully self-contained — no
templates/ or static/ folder needed), and provides a real /analyze
endpoint that:

  1. Accepts ANY image type (PNG, JPEG, WEBP, GIF, BMP, HEIC, etc.)
  2. Sends it to Claude to extract the claim/text on screen
     (English / Hindi / mixed script)
  3. Fact-checks that claim using Claude WITH the web_search tool,
     so it verifies against real, current sources
  4. Returns a single 0-100 "truePercent" score — how likely the
     claim is TRUE. The frontend derives False% as (100 - truePercent)
     and fills both meters from this one number.

------------------------------------------------------------
SETUP
------------------------------------------------------------
    pip install fastapi uvicorn python-multipart anthropic pillow pillow-heif

    Set your API key first (PowerShell):
        $env:ANTHROPIC_API_KEY="your-key-here"
    (Mac/Linux):
        export ANTHROPIC_API_KEY="your-key-here"

RUN
------------------------------------------------------------
    python lens.py
    then open http://localhost:5000

FOLDER STRUCTURE REQUIRED
    lens.py
    lens.html      <-- the standalone HTML file, same folder as lens.py
------------------------------------------------------------
"""

import os
import io
import json
import base64
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from PIL import Image
from google import genai
from dotenv import load_dotenv


 
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False


# ============================================================
# Setup
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="TruthLens AI")

load_dotenv("key.env")

API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY) if API_KEY else None

# ------------------------------------------------------------------
# DEMO MODE — True = no API key needed, returns a random-ish fake
# result so you can see the app work immediately. Set to False once
# you have a real GEMINI_API_KEY and want real fact-checking.
# ------------------------------------------------------------------
DEMO_MODE = True

MODEL = "gemini-pro-vision"

GEMINI_SUPPORTED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_DIMENSION = 1568  # px — keeps OCR quality high while staying under API limits


# ============================================================
# DEMO MODE — fake result, no API key needed
# ============================================================

def demo_analyze():
    import random
    return {
        "claim": "Drinking hot lemon water every morning cures the common cold within 24 hours.",
        "explanation": "DEMO MODE is on — this is fake data, not a real analysis. "
                        "Set DEMO_MODE = False in lens.py once you have a real "
                        "GEMINI_API_KEY for actual fact-checking.",
        "truePercent": random.randint(5, 95),
    }


# ============================================================
# STAGE 1 — Normalize ANY uploaded image type
# ============================================================

def prepare_image(image_bytes, mimetype):
    needs_conversion = mimetype not in GEMINI_SUPPORTED_TYPES

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        needs_conversion = True

    if needs_conversion:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue(), "image/jpeg"

    return image_bytes, mimetype


# ============================================================
# STAGE 2 — Read the image: extract the claim/text on screen
# ============================================================

def extract_claim(image_bytes, media_type):
    image_data = base64.b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Extract the main factual claim shown in this image "
                        "(text may be English, Hindi, or mixed). Return ONLY "
                        "the claim text, exactly as written, nothing else. "
                        "If there is no readable claim, return exactly: NO_TEXT_FOUND"
                    ),
                },
            ],
        }],
    )
  
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return "" if text == "NO_TEXT_FOUND" else text


# ============================================================
# STAGE 3 — Fact-check WITH internet access (web_search tool)
# Returns a single 0-100 "how true is this" score.
# ============================================================

def fact_check(claim_text):
    prompt = f"""Fact-check this claim: "{claim_text}"

Search the web to verify it against current, reliable sources before
answering — do not rely on memory alone.

Respond with ONLY valid JSON in exactly this format, no markdown
fences, no text outside the JSON:
{{
  "true_percent": 0,
  "explanation": "2-3 sentence explanation of your reasoning, written in the same language as the claim"
}}

"true_percent" is a single number from 0 to 100 representing how
likely the claim is TRUE:
  - 90-100: strongly confirmed true by reliable sources
  - 60-89: mostly true / true with minor caveats
  - 40-59: mixed, unclear, or genuinely unverifiable
  - 11-39: mostly false / misleading
  - 0-10: strongly confirmed false by reliable sources"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    return parse_json_safely(raw)


def parse_json_safely(raw_text):
    if not raw_text:
        return {"error": "Empty response from model"}

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {"error": "Could not parse model output", "raw": raw_text}


# ============================================================
# Routes
# ============================================================

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "lens.html")


@app.post("/analyze")
async def analyze(image: UploadFile = File(...)):
    try:
        if not image.filename:
            return JSONResponse({"error": "No file selected"}, status_code=400)

        image_bytes = await image.read()
        if not image_bytes:
            return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)

        # --- DEMO MODE: skip real API calls entirely ---
        if DEMO_MODE:
            return demo_analyze()

        if client is None:
            return JSONResponse({
                "error": "GEMINI_API_KEY is not set on the server. "
                         "Set it as an environment variable and restart lens.py."
            }, status_code=500)

        mimetype = image.content_type or "image/png"

        # --- Stage 1: normalize (accepts ANY image type) ---
        try:
            image_bytes, media_type = prepare_image(image_bytes, mimetype)
        except Exception as e:
            return JSONResponse({
                "error": f"Could not read this image file: {str(e)}. "
                         f"Try a PNG or JPEG screenshot instead."
            }, status_code=400)

        # --- Stage 2: extract the claim from the image ---
        claim = extract_claim(image_bytes, media_type)
        if not claim:
            return JSONResponse(
                {"error": "No readable claim found in the image"}, status_code=400
            )

        # --- Stage 3: fact-check with internet search ---
        result = fact_check(claim)
        if "error" in result:
            return JSONResponse(result, status_code=502)

        true_percent = result.get("true_percent", 50)
        try:
            true_percent = max(0, min(100, int(true_percent)))
        except (TypeError, ValueError):
            true_percent = 50

        return {
            "claim": claim,
            "explanation": result.get("explanation", ""),
            "truePercent": true_percent,
        }

    except genai.APIStatusError as e:
        print("GEMINI API ERROR:", str(e))
        return JSONResponse({"error": f"Gemini API error: {str(e)}"}, status_code=502)

    except Exception as e:
        print("UNEXPECTED ERROR in /analyze:")
        traceback.print_exc()
        return JSONResponse({"error": f"Server error: {str(e)}"}, status_code=500)


# ============================================================
# Run — `python lens.py` starts the server directly
# ============================================================

if __name__ == "__main__":
    import uvicorn

    if DEMO_MODE:
        print("=" * 70)
        print("DEMO MODE IS ON — no API key needed, no real analysis happens.")
        print("Set DEMO_MODE = False in lens.py once you have a real")
        print("ANTHROPIC_API_KEY and want real fact-checking.")
        print("=" * 70)
    if not API_KEY and not DEMO_MODE:
        print("=" * 70)
        print("WARNING: ANTHROPIC_API_KEY is not set.")
        print('    $env:ANTHROPIC_API_KEY="your-key-here"   (PowerShell)')
        print('    export ANTHROPIC_API_KEY="your-key-here" (Mac/Linux)')
        print("=" * 70)
    if not HEIC_SUPPORTED:
        print("NOTE: pillow-heif not installed — iPhone HEIC photos may fail.")
        print("      Install with: pip install pillow-heif")

    uvicorn.run("lens:app", host="127.0.0.1", port=5000, reload=True)