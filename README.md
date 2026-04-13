# Autonomous AI Job Agent: Hybrid Vision & HITL Edition

## 🎯 Executive Summary
This project is an advanced **AI-driven Data Pipeline** designed to automate market monitoring and the job application lifecycle. Unlike standard automation scripts, this agent utilizes a **Hybrid LLM Architecture** and a **Human-in-the-Loop (HITL)** framework to ensure high precision in complex, non-deterministic web environments (LinkedIn).



## 🏗 Architectural Overview
The system is built as a multi-stage pipeline, mimicking enterprise data processing workflows:

1.  **Data Ingestion:** Real-time web-scraping of unstructured job market data via **Playwright**.
2.  **Intelligent Evaluation (Flash Layer):** Utilizing `gemini-2.5-flash` for high-speed semantic matching between a candidate's CV (PDF) and job descriptions.
3.  **Human-in-the-Loop (HITL) Gate:** An interactive Telegram integration that requires explicit human approval before proceeding, ensuring 100% control over the application "Golden Copy."
4.  **Visual Interaction Engine (Pro Layer):** Using multimodal `gemini-2.5-pro` (Vision) to analyze UI screenshots in real-time, handling dynamic modals, radio buttons, and complex form logic without brittle CSS selectors.
5.  **State Management:** Local persistence of "learned" answers and processed IDs to prevent redundant operations and build a long-term knowledge base.



## 🛠 Tech Stack
* **Orchestration:** Python 3.10+
* **Automation:** Playwright (Chromium)
* **AI Models:** Google Gemini 2.5 Pro (Vision/Reasoning) & Flash (Extraction/Matching)
* **Interface:** Telegram Bot API (Async Notification & Control)
* **Security:** Decoupled configuration via `.env` and specialized `.gitignore` protocols.

## 🚀 Key Differentiators for Data Platforms
* **Multimodal UI Navigation:** Instead of traditional "find element by ID," the agent "sees" the screen like a human, making it resilient to UI updates.
* **Automated Profiling & Salary Estimation:** Uses RAG-like logic to compare CV experience against market requirements, providing a direct "Verdict" and "Salary Range" suggestion.
* **Rate-Limit Awareness:** Built-in retry logic and exponential backoff for API stability.
* **Human-Centric Design:** The agent pings the user for edge cases (e.g., "How many years of experience do you have with Snowflake?") and remembers the answer for future iterations.



## 🔧 Setup & Configuration

1. **Clone & Install:**
   ```bash
   git clone [https://github.com/yourusername/job-agent-visual.git](https://github.com/yourusername/job-agent-visual.git)
   cd job-agent-visual
   pip install -r requirements.txt
   playwright install chromium