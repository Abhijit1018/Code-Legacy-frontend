# Legacy Modernizer

Welcome to **Legacy Modernizer**, an end-to-end full-stack AI platform designed to translate and modernize legacy codebases (like COBOL) into modern languages (like Python or Go) with high precision.

This repository encompasses both the robust **Python FastAPI backend** orchestration engine and the intuitive **React Vite frontend**.

## 🚀 Features
- **AI-Powered Code Translation:** Convert entire repositories from one language to another automatically.
- **Smart Context Compression:** Integrates the **ScaleDown** context optimizer out of the box to drastically reduce prompt token sizes (saving LLM costs) while maintaining semantic meaning using AST-guided code retrieval.
- **Full Customizability:** Exclude comments, exclude tests, and pass custom instruction overrides to the LLM per analysis.
- **Dynamic AI Selection:** Built-in UI to hot-swap between multiple free and paid LLMs on the fly. Models like NVIDIA Nemotron-3 120B and standard DeepSeek/Claude 3.5 are easily configurable.

## 🏗️ Architecture Stack
* **Frontend:** Built with React 18, Vite, and Monaco Editor for dynamic UI visualization.
* **Backend:** Python, FastAPI, Uvicorn, and Pydantic orchestrate the backend state.
* **Core Modernizer:** Custom AST parsing, context detection, and LLM transformation workflows handled by our `legacy_modernizer` engine.
* **LLM Hub:** Requests are dispatched via OpenRouter to seamlessly switch models based on rate limits.

---

## 🛠️ Quick Start Guide

### 1. Configure the Environment
Clone the repository and install the `.env` configuration file in the project root:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
SCALEDOWN_API_KEY=your_scaledown_api_key_here

# Required for some IDE setups
PYTHONPATH=.
```

### 2. Run the Backend API
The FastAPI backend serves both the repository analysis logic and raw code snippet translation interfaces.
```bash
python -m venv venv
# Activate the virtual environment (.venv/Scripts/activate or source .venv/bin/activate)
pip install -r backend/requirements.txt

# Start the server:
uvicorn backend.app.main:app --reload --port 8000
```
*The api and interactive swagger docs will be available at `http://localhost:8000/docs`.*

### 3. Run the Frontend UI
The UI is a React application built with Vite handling all user interaction parameters.
```bash
cd frontend
npm install
npm run dev
```
*The web interface will be available at `http://localhost:5173/`.*

---

## 💻 Easy Deployment (Render + Vercel)
This mono-repo design is built to be split-hosted for free:
- **Backend (Render):** Deploy the repo directly as a Render Web Service. Set the root to `/`, the build command to `pip install -r backend/requirements.txt`, and start command to `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. 
- **Frontend (Vercel):** Create a new Vercel project, select the `/frontend` sub-directory as the root directory, and set `VITE_API_URL` to point to your new Render backend URL!

--- 
*This software utilizes advanced Language Models to generate code. Always review translated outputs before integrating into production environments.*
