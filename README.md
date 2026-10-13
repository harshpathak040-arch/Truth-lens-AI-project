# 🔍 TruthLens AI

**AI-Powered Fact-Checking and Claim Analysis Tool**

TruthLens AI is an AI-powered fact-checking project designed to help users analyze claims from text, images, and screenshots. It uses AI to evaluate the provided content, identify potentially misleading information, and generate an analysis with a confidence score.

## Features

- **Text Analysis:** Analyze claims and statements for potential misinformation.
- **Image Analysis:** Extract and analyze claims from uploaded images.
- **Screenshot Analysis:** Analyze captured screenshots to evaluate the information they contain.
- **AI-Powered Verification:** Use Google's Gemini API to analyze claims and generate explanations.
- **Confidence Meter:** Display an estimated confidence score for the analysis.
- **File Upload:** Submit supported files for analysis.
- **Analysis History:** Access previous analyses through the history interface.
- **Browser Extension:** Provide a convenient interface for analyzing claims through a browser popup.

## 🛠️ Tech Stack

**Backend**
- Python
- FastAPI
- Google Gemini API

**Frontend**
- HTML
- CSS
- JavaScript

**Tools**
- Visual Studio Code
- Git and GitHub

## ⚙️ Installation and Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd TruthLens-AI
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

If the project contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Configure the API Key

Create a `.env` file in the project directory and add your Gemini API key:

```env
GEMINI_API_KEY=your_api_key_here
```

Never upload your real API key to GitHub.

### 5. Start the Backend

Run the FastAPI application using the appropriate module name for your project. For example, if the entry file is `main.py`:

```bash
python -m uvicorn main:app --reload
```

Open the API documentation at:

`http://127.0.0.1:8000/docs`

### 6. Run the Frontend

Open the frontend using your configured local server or load the extension into your browser through its extension management page.

Follow the project's folder structure and configuration for the exact startup process.

## 🔄 How It Works

1. The user submits text, an image, or a screenshot.
2. The backend receives and processes the content.
3. The Gemini API analyzes the available information.
4. TruthLens AI presents the analysis, explanation, and confidence estimate.
5. The user reviews the result and can access previous analyses where supported.

## 🎯 Project Goals

- Make claim analysis accessible and convenient.
- Help users recognize potentially misleading information.
- Encourage critical thinking and responsible information sharing.
- Explore practical applications of AI in fact-checking.

## Disclaimer

TruthLens AI provides AI-generated analysis and is not a substitute for independent verification using reliable sources. AI-generated results and confidence scores may be inaccurate. Important claims should be checked against trustworthy, primary sources.

##  creater

**Harsh Pathak**

Developed as an AI-powered fact-checking project.

---

⭐ If you find this project interesting, consider giving the repository a star!