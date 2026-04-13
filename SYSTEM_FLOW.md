# Visual System Flowchart

This flowchart visualizes the agent's logic, decision-making nodes, and the separation of concerns between the Fast (Text) and Pro (Vision) LLM layers. GitHub renders this diagram automatically.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#005fcc', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#fff'}}}%%

graph TB;
    %% --- External Elements ---
    subgraph EXTERNAL [External Sources]
        LinkedIn[LinkedIn Job Search]
        TelegramUser[Telegram User]
    end

    %% --- Internal Data Layer ---
    subgraph DATA_LAYER [Internal Data & Memory]
        CV_PDF[Leon CV .pdf]
        ENV_VARS[.env Config]
        LEARNED_ANS[learned_answers.json]
        PROC_IDS[processed_jobs.json]
    end

    %% --- Execution Layer ---
    subgraph EXECUTION [Python Orchestrator with Playwright]
        AGENT(Start run_agent)
        INIT_PROF(Parse CV & Generate Reference Profile)
        LAUNCH_BROWSER(Launch Chromium Session)
    end

    %% --- Evaluation Layer (Fast LLM) ---
    subgraph EVALUATION [Match-Evaluation Pipeline]
        E_GEMINI_FLASH{{AI: Google Gemini 2.5 Flash}}
        SCRAPE(Playwright: Extract Job Title & Description)
        E_MATCH_EVAL(CV vs Job Description semantic matching)
    end

    %% --- Interaction Layer (Telegram/HITL) ---
    subgraph INTERACTION [HITL / C2 Gate]
        TG_SEND(Telegram Bot: Send Match Report & Action Buttons)
        TG_WAIT_APPROVE{Wait for User: Apply or Skip?}
    end

    %% --- Navigation Layer (Vision LLM) ---
    subgraph NAVIGATION [Visual Interaction Engine]
        V_GEMINI_PRO{{AI: Google Gemini 2.5 Pro Vision}}
        V_SCREEN(Playwright: Take Screenshot of Modal)
        V_VISION_ANALYSIS(Spatial Analysis & Action Logic Generation)
        V_ACTION_EXEC(Playwright: Execute Field Fills, Clicks, Selects)
        V_LOOP_CHECK{Step Loop Count < 15?}
        V_DISMISS(Playwright: Dismiss Modal/Discard Application)
    end

    %% --- Core Flows ---
    START(System Start) --> ENV_VARS
    ENV_VARS --> AGENT
    AGENT --> CV_PDF
    CV_PDF --> INIT_PROF
    INIT_PROF --> LAUNCH_BROWSER
    LAUNCH_BROWSER --> LinkedIn
    LinkedIn --> SCRAPE
    SCRAPE --> E_GEMINI_FLASH
    E_GEMINI_FLASH --> E_MATCH_EVAL
    E_MATCH_EVAL --> TG_SEND
    TG_SEND --> TG_WAIT_APPROVE

    %% --- Decision Paths ---
    TG_WAIT_APPROVE -- "Skip" --> PROC_IDS
    PROC_IDS --> LinkedIn

    TG_WAIT_APPROVE -- "Apply" --> V_SCREEN
    V_SCREEN --> V_GEMINI_PRO
    V_GEMINI_PRO --> V_VISION_ANALYSIS
    V_VISION_ANALYSIS --> V_LOOP_CHECK

    V_LOOP_CHECK -- "Continue" --> V_ACTION_EXEC
    V_ACTION_EXEC --> V_SCREEN

    V_LOOP_CHECK -- "Ask User (e.g., Salary)" --> TG_SEND_Q(Telegram Bot: Send Question)
    TG_SEND_Q --> TelegramUser
    TelegramUser --> LEARNED_ANS
    LEARNED_ANS --> V_SCREEN

    V_LOOP_CHECK -- "Submit Application" --> V_SUBMIT(Playwright: Click Submit)
    V_SUBMIT --> PROC_IDS

    V_LOOP_CHECK -- "Timeout/Error" --> V_DISMISS
    V_DISMISS --> PROC_IDS

    %% --- Styling for Roles ---
    %% Python Code = Blue, Playwright = Dark Blue, Gemini = Purple, TG = Yellow, JSON = Gray
    classDef python fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef playwright fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,stroke-dasharray: 5 5;
    classDef gemini fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,rx:15,ry:15;
    classDef telegram fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef data fill:#eeeeee,stroke:#616161,stroke-width:1px;
    classDef external fill:#fff,stroke:#333,stroke-width:1px,stroke-dasharray: 2 2;

    class AGENT,INIT_PROF,LAUNCH_BROWSER,START,MARK_APPLIED python;
    class SCRAPE,LAUNCH_BROWSER,V_SCREEN,V_ACTION_EXEC,V_SUBMIT,V_DISMISS playwright;
    class E_GEMINI_FLASH,V_GEMINI_PRO gemini;
    class TG_SEND,TG_SEND_Q,TelegramUser telegram;
    class CV_PDF,ENV_VARS,LEARNED_ANS,PROC_IDS data;
    class LinkedIn external;