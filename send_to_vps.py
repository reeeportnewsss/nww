import os
import sys
import logging
import requests
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime

# ==== CONFIGURATION ====
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")  # must be set

if not all([GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    sys.stderr.write("ERROR: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID must all be set\n")
    sys.exit(1)

NEWS_FILE   = "processed_stock_news.txt"
OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "/tmp")
MODEL_ID    = "gemini-2.5-flash-preview-05-20"

# ==== SETUP LOGGING ====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gemini_file.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==== MAKE SURE OUTPUT DIR EXISTS ====
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==== INITIALIZE GEMINI CLIENT ====
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
try:
    client = genai.Client()
    logger.info("Gemini client initialized.")
except Exception as e:
    logger.error("Failed to initialize Gemini client: %s", e)
    client = None

# ==== HELPERS ====

def read_news_file():
    """Read the entire content of processed_stock_news.txt or return a default message."""
    if not os.path.exists(NEWS_FILE):
        logger.warning("News file %s not found.", NEWS_FILE)
        return "No news titles available from the provided file."
    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        logger.info("Loaded news content from %s", NEWS_FILE)
        return content or "No news titles available from the provided file."
    except Exception as e:
        logger.error("Error reading news file: %s", e)
        return f"Error reading news file: {e}"

def send_to_telegram(text, chat_id=None, bot_token=None):
    """Send a text message to Telegram, with Markdown enabled."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    bot_token = bot_token or TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code != 200:
            logger.error("Telegram sendMessage failed (%s): %s", resp.status_code, resp.text)
            logger.debug("URL: %s\nPayload: %s", url, payload)
            return False
        return True
    except Exception as e:
        logger.error("Exception sending message to Telegram: %s", e)
        logger.debug("URL: %s\nPayload: %s", url, payload)
        return False

def send_file_to_telegram(file_path, chat_id=None, bot_token=None):
    """Send a local file to Telegram as a document."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    bot_token = bot_token or TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as doc:
            files = {"document": doc}
            data  = {"chat_id": chat_id}
            resp = requests.post(url, files=files, data=data, timeout=30)
        if resp.status_code != 200:
            logger.error("Telegram sendDocument failed (%s): %s", resp.status_code, resp.text)
            logger.debug("URL: %s", url)
            return False
        return True
    except Exception as e:
        logger.error("Exception sending file to Telegram: %s", e)
        return False

def save_and_send_report(body_text):
    """Save the generated text to a dated .txt, then send a summary + the file."""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"corporate_news_{today}.txt"
    path = os.path.join(OUTPUT_DIR, filename)

    # build content
    content = (
        "=== Indian Corporate News Analysis ===\n\n"
        f"**Best News Item from File**\n{body_text}\n\n"
        f"Generated on: {today}\n"
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Report saved to %s", path)
    except Exception as e:
        logger.error("Failed to write report: %s", e)
        return False

    # send summary & file
    summary = (
        "📊 *Corporate News Analysis Report*\n\n"
        f"📅 Date: {today}\n\n"
        "📋 Report generated and ready for review!"
    )
    ok = send_to_telegram(summary)
    if not send_file_to_telegram(path):
        ok = False
        # fallback to sending the content as plain text if short enough
        if len(content) <= 4000:
            send_to_telegram(f"```\n{content}\n```")
    return ok

# ==== MAIN LOGIC ====

def main():
    if client is None:
        err = "Failed to initialize Gemini client. Check your API key."
        logger.error(err)
        send_to_telegram(f"❌ *Error*\n\n{err}")
        return

    prompt = read_news_file()
    logger.info("Querying Gemini for analysis…")
    try:
        resp = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=10000
                ),
                response_modalities=["TEXT"]
            )
        )
        # assemble the answer
        parts = resp.candidates[0].content.parts
        text = ""
        for p in parts:
            if not p.text:
                continue
            tag = "Thought summary:" if p.thought else "Answer:"
            text += f"{tag}\n{p.text}\n\n"

        if save_and_send_report(text):
            logger.info("Report sent successfully.")
        else:
            logger.error("Failed to send report.")

    except Exception as e:
        err = f"Error querying Gemini API: {e}"
        logger.error(err)
        send_to_telegram(f"❌ *Error*\n\n{err}")

if __name__ == "__main__":
    main()
