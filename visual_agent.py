import sys
import os
import time
import json
import logging
import glob
import re
import requests
import PyPDF2
from PIL import Image
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Use the new GenAI SDK
from google import genai
from google.genai import types

# --- 1. SETUP LOGGING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "agent_debug.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- 2. STORAGE & MEMORY ---
MEMORY_FILE = os.path.join(BASE_DIR, "learned_answers.json")
PROCESSED_JOBS_FILE = os.path.join(BASE_DIR, "processed_jobs.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_memory(memory_dict):
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory_dict, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving memory: {e}")

def load_processed_jobs():
    if os.path.exists(PROCESSED_JOBS_FILE):
        try:
            with open(PROCESSED_JOBS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception: pass
    return set()

def save_processed_jobs(job_ids):
    try:
        with open(PROCESSED_JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(job_ids), f)
    except Exception as e:
        logger.error(f"Error saving processed jobs: {e}")

def cleanup_old_artifacts():
    files_to_remove = glob.glob(os.path.join(BASE_DIR, "step_*.png"))
    for f in files_to_remove:
        try:
            if os.path.exists(f): os.remove(f)
        except Exception: pass
    logger.info(">>> Workspace cleaned.")

# --- 3. ENVIRONMENT & API SETUP ---
load_dotenv(os.path.join(BASE_DIR, ".env"))
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CV_FILENAME = os.getenv("CV_FILENAME", "Leon_Sapranowicz_Product_Manager.pdf")
CV_PATH = os.path.join(BASE_DIR, CV_FILENAME)

EXCLUDE_KEYWORDS = ["Junior", "Intern", "Recruiter", "Sales", "Support", "Student"]

# Use the search URL from your browser
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=Warsaw&f_TPR=r86400&sortBy=DD"

if not GEMINI_API_KEY:
    logger.error(">>> CRITICAL: GEMINI_API_KEY is missing in .env")
    sys.exit(1)

# Initialize the GenAI Client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# MODEL DEFINITIONS (Combined Mode)
PRO_MODEL = 'gemini-2.5-pro'   # For Vision (UI navigation)
FLASH_MODEL = 'gemini-2.5-flash' # For Text (Matching and Profiling)

def call_gemini(model_name, contents, config=None, max_retries=3):
    """Generic wrapper for calling specified Gemini models with retry logic."""
    for attempt in range(max_retries):
        try:
            return gemini_client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                wait_time = 45 * (attempt + 1)
                logger.warning(f"   [⏳] Rate limit on {model_name}! Sleeping {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"   [!] API Error ({model_name}): {e}")
                return None
    return None

# --- 4. HELPERS ---
def extract_essential_cv(file_path):
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return " ".join([" ".join(p.extract_text().split()) for p in reader.pages])[:3500]
    except Exception: sys.exit(1)

ESSENTIAL_CV = extract_essential_cv(CV_PATH)

def send_telegram_alert(text):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": text})

def ask_telegram_and_wait(question_text, timeout_mins=5):
    url = f"https://api.telegram.org/bot{TG_TOKEN}"
    requests.post(f"{url}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": f"⚠️ ACTION REQUIRED:\n{question_text}"})
    last_update_id = 0
    try:
        res = requests.get(f"{url}/getUpdates").json()
        if res.get("result"): last_update_id = res["result"][-1]["update_id"]
    except Exception: pass
    end_time = time.time() + (timeout_mins * 60)
    while time.time() < end_time:
        try:
            res = requests.get(f"{url}/getUpdates?offset={last_update_id + 1}&timeout=10").json()
            for update in res.get("result", []):
                if "message" in update and "text" in update["message"]:
                    ans = update["message"]["text"]
                    requests.get(f"{url}/getUpdates?offset={update['update_id'] + 1}")
                    return ans
        except Exception: pass
        time.sleep(2)
    return None

def ask_telegram_confirmation(job_title, report, timeout_mins=10):
    url = f"https://api.telegram.org/bot{TG_TOKEN}"
    safe_report = report.replace("*", "").replace("_", "")
    text = f"🛑 FINAL REVIEW: {job_title}\n\n{safe_report}\n\nApply now?"
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Apply", "callback_data": "apply_yes"},
        {"text": "❌ Skip", "callback_data": "apply_no"}
    ]]}
    requests.post(f"{url}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": text, "reply_markup": keyboard})
    last_update_id = 0
    try:
        res = requests.get(f"{url}/getUpdates").json()
        if res.get("result"): last_update_id = res["result"][-1]["update_id"]
    except Exception: pass
    end_time = time.time() + (timeout_mins * 60)
    while time.time() < end_time:
        try:
            res = requests.get(f"{url}/getUpdates?offset={last_update_id + 1}&timeout=10").json()
            for update in res.get("result", []):
                if "callback_query" in update:
                    cb = update["callback_query"]
                    requests.post(f"{url}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    requests.get(f"{url}/getUpdates?offset={update['update_id'] + 1}")
                    return True if cb["data"] == "apply_yes" else False
        except Exception: pass
        time.sleep(2)
    return False

# --- 5. HYBRID AI LOGIC ---
def build_profile_from_cv(cv_text):
    """Uses FLASH model for fast text extraction."""
    prompt = f"Extract to JSON (first_name, last_name, email, phone_country_code, phone_number, location):\n{cv_text[:2000]}"
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    res = call_gemini(FLASH_MODEL, prompt, config)
    if res and res.text:
        try: return json.loads(res.text)
        except Exception: pass
    return {"first_name": "Leon", "last_name": "Sapranowicz", "email": "", "phone_country_code": "+48", "phone_number": "", "location": "Warsaw"}

def get_job_report(title, description):
    """Uses FLASH model for fast job evaluation and salary estimate."""
    prompt = f"""
    Evaluate this job against my CV as a professional career consultant.
    CV: {ESSENTIAL_CV}
    Job: {title}
    Desc: {description[:3000]}
    
    Format EXACTLY (plain text, no bold/markdown):
    🎯 MATCH: [X]%
    
    ✅ PROS:
    • [Point 1]
    • [Point 2]
    
    ⚠️ CONS:
    • [Point 1]
    • [Point 2]
    
    💰 SALARY ESTIMATE:
    Based on your profile, I suggest asking for: [Range in PLN gross/month]. Reasoning: [Short context]
    
    ⚖️ VERDICT: [Honest, direct verdict]
    """
    res = call_gemini(FLASH_MODEL, prompt, types.GenerateContentConfig(temperature=0.3))
    return res.text if res else None

def get_vision_instructions(page, step_num, current_profile, user_context="", learned_memory={}):
    """Uses PRO model for precise UI spatial analysis and form filling."""
    screenshot_path = os.path.join(BASE_DIR, f"step_{step_num}.png")
    page.wait_for_timeout(1500)
    modal = page.locator(".jobs-easy-apply-modal").first
    if modal.is_visible():
        try: modal.evaluate("el => el.scrollBy(0, 400)")
        except: page.keyboard.press("PageDown")
        page.wait_for_timeout(500)
        modal.screenshot(path=screenshot_path)
    else: page.screenshot(path=screenshot_path)
    
    img = Image.open(screenshot_path)
    mem_inj = f"\nLEARNED: {json.dumps(learned_memory)}\n" if learned_memory else ""
    ctx_inj = f"\nUSER REPLIED: '{user_context}'. Map to UI and set 'continue'.\n" if user_context else ""
    
    prompt = f"""
    Analyze LinkedIn Easy Apply screen.
    Profile: {json.dumps(current_profile)}
    CV Context: {ESSENTIAL_CV[:1000]}
    DEFAULTS: Notice: 3 months, Start: July 1st, Visa: Citizen/No sponsorship.
    DO NOT guess salaries.
    {mem_inj}{ctx_inj}
    
    Return EXACT JSON format ONLY:
    {{
      "status": "continue" | "success" | "error" | "ask_user",
      "question_for_user": "Question text if ask_user",
      "fields_to_fill": {{"Label": "Value"}},
      "radio_answers": {{"Question": "Answer (Yes/No)"}},
      "dropdowns_to_select": {{"Label": "Option"}},
      "checkboxes_to_check": ["Label"],
      "generic_clicks": ["Label"],
      "action_button": "Next/Review/Submit"
    }}
    RULES:
    1. If 'Submit application' is visible, set status 'continue' and button in 'action_button'.
    2. If screen asks for Salary/Compensation/Rate, set status to 'ask_user'.
    """
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    res = call_gemini(PRO_MODEL, [prompt, img], config)
    if res and res.text:
        try: return json.loads(res.text)
        except Exception: pass
    return None

# --- 6. UI ACTIONS ---
def smart_action(page, label, action_type, value=None):
    try:
        el = page.get_by_text(label, exact=False).first
        if not el.is_visible(): el = page.get_by_label(label, exact=False).first
        if el.is_visible():
            if action_type == "fill":
                el.click(); page.keyboard.press("Control+A"); page.keyboard.press("Backspace"); el.type(str(value), delay=30)
            elif action_type == "select":
                try: el.select_option(label=str(value), timeout=3000)
                except: el.click(); page.wait_for_timeout(500); page.keyboard.type(str(value)); page.keyboard.press("Enter")
            elif action_type == "check":
                try: el.check(timeout=1500)
                except: el.click(force=True)
            else: el.click(force=True)
            return True
        return False
    except Exception: return False

def smart_radio(page, question, answer):
    try:
        q_loc = page.get_by_text(question, exact=False).first
        if not q_loc.is_visible(): return False
        q_box = q_loc.bounding_box()
        options = page.get_by_text(answer, exact=True).all()
        best_opt, min_dist = None, float('inf')
        for opt in options:
            if opt.is_visible():
                o_box = opt.bounding_box()
                if o_box and o_box['y'] >= q_box['y'] - 10: 
                    dist = o_box['y'] - q_box['y']
                    if dist < min_dist and dist < 250: min_dist, best_opt = dist, opt
        if best_opt: best_opt.click(force=True); return True
        return False
    except Exception: return False

# --- 7. MAIN EXECUTION ---
def run_agent():
    cleanup_old_artifacts()
    agent_memory = load_memory()
    processed_ids = load_processed_jobs()
    logger.info(f">>> [V18.5] Hybrid Engine Edition (Pro + Flash). Memory: {len(agent_memory)}. Processed: {len(processed_ids)}")
    
    # Initial profile extraction using Flash
    dynamic_profile = build_profile_from_cv(ESSENTIAL_CV)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=os.path.join(BASE_DIR, "linkedin_profile"), 
            headless=False, no_viewport=True, 
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LINKEDIN_SEARCH_URL, wait_until="domcontentloaded")
        
        # Login validation loop
        logger.info(">>> Validating session...")
        end_wait = time.time() + 150
        logged_in = False
        while time.time() < end_wait:
            if page.locator(".job-card-container, [data-job-id]").count() > 0:
                logged_in = True; break
            if page.locator(".global-nav, .nav-main").count() > 0:
                logger.info("   [🔄] Redirecting to Search...")
                page.goto(LINKEDIN_SEARCH_URL); page.wait_for_timeout(5000); continue
            time.sleep(5)
        if not logged_in:
            logger.error("   [!] Login timeout. Closing."); context.close(); return

        cards = page.locator(".job-card-container, [data-job-id]").all()
        logger.info(f">>> Found {len(cards)} jobs. Commencing scan...")

        for i, card in enumerate(cards):
            job_id = card.get_attribute("data-job-id")
            if not job_id or job_id in processed_ids: continue
            try:
                page.keyboard.press("Escape"); card.click(force=True); page.wait_for_timeout(2500)
                title_el = page.locator(".job-details-jobs-unified-top-card__job-title").first
                title = title_el.inner_text().strip() if title_el.is_visible() else "Unknown"
                if any(k.lower() in title.lower() for k in EXCLUDE_KEYWORDS): continue
                
                # Fast Match/Report using Flash
                logger.info(f"--- Processing [{i+1}]: {title} ---")
                report = get_job_report(title, page.locator("#job-details").inner_text())
                processed_ids.add(job_id); save_processed_jobs(processed_ids)
                
                if report:
                    match = re.search(r"MATCH[^\d]*(\d+)", report, re.IGNORECASE)
                    if int(match.group(1)) if match else 0 >= 0: 
                        btn = page.get_by_role("button", name=re.compile("Easy Apply", re.IGNORECASE)).first
                        if btn.is_visible():
                            btn.click(); page.wait_for_timeout(2000)
                            step, loop, applied, user_ans, last_q, prev_hash = 1, 0, False, "", "", ""
                            while step <= 15:
                                submit = page.get_by_role("button", name=re.compile("Submit application", re.IGNORECASE)).first
                                if submit.is_visible():
                                    if ask_telegram_confirmation(title, report):
                                        submit.click(); page.wait_for_timeout(3000); applied = True
                                    else: break
                                
                                # Precise Vision using Pro
                                logger.info(f"   [Step {step}] Analyzing UI (Pro Model)...")
                                instr = get_vision_instructions(page, step, dynamic_profile, user_ans, agent_memory)
                                if not instr: break
                                
                                curr_hash = json.dumps(instr, sort_keys=True)
                                if curr_hash == prev_hash: loop += 1
                                else: loop, prev_hash = 0, curr_hash
                                if loop >= 2:
                                    ans = ask_telegram_and_wait("I'm stuck. Guide me:")
                                    if ans: user_ans = ans; continue
                                    else: break
                                    
                                if instr.get("status") == "success":
                                    applied = True
                                    btn_done = page.get_by_role("button", name=re.compile("Done", re.IGNORECASE)).first
                                    if btn_done.is_visible(): btn_done.click()
                                    else: page.keyboard.press("Escape")
                                    break
                                    
                                if instr.get("status") == "ask_user":
                                    last_q = instr.get("question_for_user", "Field check.")
                                    reply = ask_telegram_and_wait(last_q); 
                                    if reply: user_ans = reply; continue
                                    else: break
                                    
                                if user_ans and last_q: agent_memory[last_q] = user_ans; save_memory(agent_memory); user_ans, last_q = "", ""
                                
                                for q, a in instr.get("radio_answers", {}).items(): smart_radio(page, q, a)
                                for k, v in instr.get("fields_to_fill", {}).items(): smart_action(page, k, "fill", v)
                                for k, v in instr.get("dropdowns_to_select", {}).items(): smart_action(page, k, "select", v)
                                for k in instr.get("checkboxes_to_check", []): smart_action(page, k, "check")
                                for k in instr.get("generic_clicks", []): smart_action(page, k, "click")
                                
                                act_btn = instr.get("action_button")
                                if act_btn and "submit" not in act_btn.lower(): smart_action(page, act_btn, "click"); page.wait_for_timeout(3000)
                                step += 1
                            if not applied:
                                d_btn = page.locator("button[aria-label='Dismiss']").first
                                if d_btn.is_visible(): d_btn.click()
                                disc = page.get_by_role("button", name="Discard").first
                                if disc.is_visible(): disc.click()
                                page.keyboard.press("Escape")
                time.sleep(5)
            except Exception as e: logger.error(f"Error: {e}")
        context.close()

if __name__ == "__main__":
    run_agent()