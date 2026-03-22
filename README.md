<div align="center">
  <h1>✨ Legacy Modernizer ✨</h1>
  <p><strong>An Intelligent, Full-Stack AI Platform for Translating Decades-Old Code into the Future.</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com)
  [![React](https://img.shields.io/badge/React-18.0+-61dafb.svg)](https://react.dev/)
  [![Vite](https://img.shields.io/badge/Vite-5.0+-646cff.svg)](https://vitejs.dev/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

<hr/>

## 📖 Overview

Upgrading Enterprise code—like monolithic COBOL programs—is historically expensive and prone to human error. **Legacy Modernizer** completely solves this by putting a deterministic AI translator exactly where developers need it.

Using a custom React UI, developers can instantly point the orchestration engine at any GitHub repository. Behind the scenes, the Python backend parses the legacy Abstract Syntax Tree (AST), compresses the dense context to save on API budgets, and seamlessly translates the architecture into modern, maintainable code using state-of-the-art Large Language Models.

---

## ⚡ Core Features

- 🧠 **AI-Powered Code Translation:** Convert entire legacy repositories into modern languages (e.g., Python, Go) automatically.
- 🗜️ **Smart Context Compression (ScaleDown):** Stop exceeding LLM context windows! We integrate **ScaleDown** out of the box to compress prompt token sizes using semantic embedding searches and AST-guided structural retrieval.
- 🎛️ **Full Developer Control:** Exclude verbose comments, strip out old tests, and inject custom instruction prompts per-analysis to steer the translation logic.
- 🔄 **Dynamic LLM Routing:** Swap between models on the fly! Effortlessly switch between free high-tier models (`NVIDIA Nemotron 120B`, `Llama 3.3 70B`, `GLM-4.5`) or commercial standards via **OpenRouter** to bypass strict rate limits.

---

## 🏗️ Architecture Stack

- **Frontend:** Built with React 18 & Vite. Dynamic code visualization powered by **Monaco Editor**.
- **Backend:** High-performance REST API driven by **Python**, **FastAPI**, and **Uvicorn**.
- **Transformation Engine:** Core `legacy_modernizer` engine orchestrates AST parsing, context detection, and translation mapping.
- **LLM Hub:** All requests are safely dispatched and queued via OpenRouter to seamlessly switch models based on rate limits.

---

## 💡 The Problem We Solved

Building this platform from scratch involved navigating immense technical challenges:
1. **The Context Window Barrier:** We bypassed absolute token limits by integrating `HASTE` and `FAISS` semantic embedding optimizations, preventing API errors before they occur.
2. **Server Deadlocks:** Mass translations trigger aggressive LLM `429 Too Many Requests` limits. We implemented highly fault-tolerant asynchronous exponential backoff with instant model fallbacks to keep the Uvicorn server permanently responsive.
3. **Monorepo Environment Pathing:** We conquered strict Pyright/VS Code static import resolution by dynamically building `sys.path` and injecting custom IDE settings directly into the workspace.

---

## 🚀 Quick Start Guide

### 1. Environment Configuration
Clone the repository and set up the `.env` configuration file in the project root:
```env
# Required for translations
OPENROUTER_API_KEY=your_openrouter_api_key_here
SCALEDOWN_API_KEY=your_scaledown_api_key_here

# Required for strict IDE analysis (e.g., VS Code)
PYTHONPATH=.
```

### 2. Run the Backend API 🐍
```bash
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```
*Checkout the interactive Swagger docs at `http://localhost:8000/docs`.*

### 3. Run the Frontend UI ⚛️
```bash
cd frontend
npm install
npm run dev
```
*The web interface is instantly hot-reloaded at `http://localhost:5173/`.*

---

## ☁️ Zero-Cost Deployment

This mono-repo is specifically designed to be split-hosted natively for free:
- **Backend (Render.com):** Deploy the repo directly as a Render Web Service. Set the root to `/`, the build command to `pip install -r backend/requirements.txt`, and start command to `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. 
- **Frontend (Vercel.com):** Import the repository into Vercel, set the root directory to `frontend`, and configure your `VITE_API_URL` environment variable to point to your new Render backend!

<br>
<div align="center">
  <i>This software utilizes advanced Language Models to generate code. Always review translated outputs before integrating into production environments.</i><br><br>
  Built with ❤️ for code modernization.
</div>
