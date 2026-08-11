import os
import io
import json
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from google import genai
from google.genai import types
from dotenv import load_dotenv


# ============================================================
# SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TruthLens AI")


# ============================================================
# CORS
# Allows the Chrome extension to communicate with FastAPI
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOAD API KEY
# ============================================================

load_dotenv(BASE_DIR / "key.env")

API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY) if API_KEY else None


# ============================================================
# SETTINGS
# ============================================================

# False = use real Gemini API
# True = use fake demo data
DEMO_MODE = False

# Gemini model
MODEL = "gemini-3.5-flash"

GEMINI_SUPPORTED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif"
}

MAX_DIMENSION = 1568


# ============================================================
# HEIC SUPPORT
# ============================================================

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True

except ImportError:
    HEIC_SUPPORTED = False


# ============================================================
# DEMO MODE
# ============================================================

def demo_analyze():

    import random

    return {
        "claim": (
            "Drinking hot lemon water every morning "
            "cures the common cold within 24 hours."
        ),

        "explanation": (
            "DEMO MODE is active. "
            "This is fake data and not a real analysis."
        ),

        "truePercent": random.randint(5, 95)
    }


# ============================================================
# PREPARE IMAGE
# ============================================================

def prepare_image(image_bytes, mimetype):

    needs_conversion = mimetype not in GEMINI_SUPPORTED_TYPES

    img = Image.open(io.BytesIO(image_bytes))

    img = img.convert("RGB")

    if max(img.size) > MAX_DIMENSION:

        img.thumbnail(
            (MAX_DIMENSION, MAX_DIMENSION)
        )

        needs_conversion = True

    if needs_conversion:

        buffer = io.BytesIO()

        img.save(
            buffer,
            format="JPEG",
            quality=90
        )

        return buffer.getvalue(), "image/jpeg"

    return image_bytes, mimetype


# ============================================================
# STAGE 1
# EXTRACT CLAIM FROM IMAGE
# ============================================================

def analyze_image(image_bytes, media_type):

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=media_type
    )

    prompt = """
You are TruthLens, an AI fact-checking assistant.

Analyze all factual claims present in this image.

The image may contain English, Hindi, Hinglish, or multiple claims.

Return ONLY valid JSON in exactly this format:

{
    "claim": "Brief summary of the main claims",
    "true_percent": 0,
    "explanation": "Explain which claims are true, false, or misleading."
}

true_percent means how likely the overall information is TRUE.

90-100 = strongly true
70-89 = mostly true
50-69 = mixed or partially true
30-49 = mostly false
0-29 = strongly false

If there are multiple claims, consider ALL of them.

Do not use Google Search.
Do not add markdown.
Do not add ```json.
Return ONLY the JSON object.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            image_part,
            prompt
        ]
    )

    return parse_json_safely(response.text)


# ============================================================
# STAGE 2
# FACT CHECK USING GOOGLE SEARCH
# ============================================================

def fact_check(claim_text):

    prompt = f"""
You are a professional fact-checking AI.

Fact-check this claim:

"{claim_text}"

Use Google Search to verify the claim against current,
reliable sources.

Do not rely only on your memory.

Return ONLY valid JSON in this exact format:

{{
    "true_percent": 0,
    "explanation": "2-3 sentence explanation of your reasoning."
}}

Rules for true_percent:

90-100 = strongly confirmed true
60-89 = mostly true / true with minor caveats
40-59 = mixed, unclear, or unverifiable
11-39 = mostly false / misleading
0-10 = strongly confirmed false

Write the explanation in the same language as the claim.
"""

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
        max_output_tokens=1000
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config
    )

    raw = response.text.strip()

    return parse_json_safely(raw)


# ============================================================
# SAFE JSON PARSER
# ============================================================

def parse_json_safely(raw_text):

    if not raw_text:

        return {
            "error": "Empty response from Gemini"
        }

    cleaned = raw_text.strip()

    # Remove markdown code fences
    if cleaned.startswith("```"):

        lines = cleaned.splitlines()

        # Remove first line: ``` or ```json
        if lines:
            lines = lines[1:]

        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    # --------------------------------------------------------
    # 1. Try direct JSON
    # --------------------------------------------------------

    try:

        return json.loads(cleaned)

    except json.JSONDecodeError:

        pass

    # --------------------------------------------------------
    # 2. Try extracting JSON object from extra text
    # --------------------------------------------------------

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:

        json_text = cleaned[start:end + 1]

        try:

            return json.loads(json_text)

        except json.JSONDecodeError:

            pass

    # --------------------------------------------------------
    # 3. Return useful error
    # --------------------------------------------------------

    return {
        "error": "Could not parse Gemini response",
        "raw": raw_text
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return FileResponse(
        BASE_DIR / "lens.html"
    )


# ============================================================
# ANALYZE IMAGE
# ============================================================

@app.post("/analyze")
async def analyze(
    image: UploadFile = File(...)
):

    try:

        # ----------------------------------------------------
        # FILE CHECK
        # ----------------------------------------------------

        if not image.filename:

            return JSONResponse(
                {
                    "error": "No file selected"
                },
                status_code=400
            )

        image_bytes = await image.read()

        if not image_bytes:

            return JSONResponse(
                {
                    "error": "Uploaded file is empty"
                },
                status_code=400
            )

        # ----------------------------------------------------
        # DEMO MODE
        # ----------------------------------------------------

        if DEMO_MODE:

            return demo_analyze()

        # ----------------------------------------------------
        # API KEY CHECK
        # ----------------------------------------------------

        if client is None:

            return JSONResponse(
                {
                    "error": (
                        "GEMINI_API_KEY is not set. "
                        "Check your key.env file."
                    )
                },
                status_code=500
            )

        # ----------------------------------------------------
        # IMAGE TYPE
        # ----------------------------------------------------

        mimetype = (
            image.content_type
            or "image/png"
        )

        # ----------------------------------------------------
        # PREPARE IMAGE
        # ----------------------------------------------------

        try:

            image_bytes, media_type = prepare_image(
                image_bytes,
                mimetype
            )

        except Exception as e:

            return JSONResponse(
                {
                    "error": (
                        f"Could not read image: {str(e)}"
                    )
                },
                status_code=400
            )

        # ----------------------------------------------------
        # ANALYZE IMAGE
        # ----------------------------------------------------

        result = analyze_image(
            image_bytes,
            media_type
        )

        if "error" in result:

            return JSONResponse(
                result,
                status_code=502
            )

        # ----------------------------------------------------
        # TRUE PERCENT
        # ----------------------------------------------------

        true_percent = result.get(
            "true_percent",
            50
        )

        try:

            true_percent = int(
                true_percent
            )

            true_percent = max(
                0,
                min(100, true_percent)
            )

        except (TypeError, ValueError):

            true_percent = 50

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {

            "claim": result.get(
                "claim",
                ""
            ),

            "explanation": result.get(
                "explanation",
                ""
            ),

            "truePercent": true_percent
        }

    except Exception as e:

        print("\n========== ERROR ==========")

        traceback.print_exc()

        print("===========================\n")

        return JSONResponse(
            {
                "error": f"Server error: {str(e)}"
            },
            status_code=500
        )


# ============================================================
# BROWSER EXTENSION API
# ============================================================
# The Chrome extension sends screenshots here.
#
# It uses the same analysis function as /analyze.
# ============================================================

@app.post("/api/analyze-file")
async def analyze_file(
    image: UploadFile = File(...)
):

    return await analyze(image)


# ============================================================
# HEALTH CHECK
# ============================================================
# Useful for checking whether TruthLens backend is running.
# ============================================================

@app.get("/api/health")
def health_check():

    return {
        "status": "online",
        "service": "TruthLens AI"
    }


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    print("=" * 70)
    print("TRUTHLENS AI")
    print("=" * 70)

    if DEMO_MODE:

        print(
            "DEMO MODE: ON"
        )

    else:

        if API_KEY:

            print(
                "GEMINI API: CONNECTED"
            )

        else:

            print(
                "WARNING: GEMINI_API_KEY NOT FOUND"
            )

            print(
                "Check key.env"
            )

    if not HEIC_SUPPORTED:

        print(
            "NOTE: pillow-heif is not installed."
        )

        print(
            "Install with: pip install pillow-heif"
        )

    print("=" * 70)

    uvicorn.run(
        "lens:app",
        host="127.0.0.1",
        port=5000,
        reload=True
    )