import os
import sys
import logging
import requests
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime

# ==== CONFIGURATION WITH DEBUGGING ====
print("=== ENVIRONMENT VARIABLES DEBUG ===")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Debug output
print(f"GEMINI_API_KEY found: {'Yes' if GEMINI_API_KEY else 'No'}")
print(f"TELEGRAM_BOT_TOKEN found: {'Yes' if TELEGRAM_BOT_TOKEN else 'No'}")
print(f"TELEGRAM_CHAT_ID found: {'Yes' if TELEGRAM_CHAT_ID else 'No'}")

if GEMINI_API_KEY:
    print(f"GEMINI_API_KEY (partial): {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-5:]}")
if TELEGRAM_BOT_TOKEN:
    print(f"TELEGRAM_BOT_TOKEN (partial): {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-10:]}")
if TELEGRAM_CHAT_ID:
    print(f"TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

print("=== END DEBUG ===\n")

# Fallback values for testing (REMOVE THESE IN PRODUCTION)
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables!")
if not TELEGRAM_BOT_TOKEN:
    print("WARNING: TELEGRAM_BOT_TOKEN not found in environment variables!")
    # Temporary fallback - REMOVE IN PRODUCTION
    
    print("Using hardcoded TELEGRAM_BOT_TOKEN for testing")
if not TELEGRAM_CHAT_ID:
    print("WARNING: TELEGRAM_CHAT_ID not found in environment variables!")
    # Temporary fallback - REMOVE IN PRODUCTION
    TELEGRAM_CHAT_ID = "1486785506"
    print("Using hardcoded TELEGRAM_CHAT_ID for testing")

# Check if we have minimum required credentials
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("ERROR: Missing Telegram credentials")
    sys.exit(1)

NEWS_FILE = "processed_stock_news.txt"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp")
MODEL_ID = "gemini-2.5-flash-preview-05-20"

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
client = None
if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
    try:
        client = genai.Client()
        logger.info("Gemini client initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize Gemini client: %s", e)
else:
    logger.warning("GEMINI_API_KEY not provided. Gemini features will be disabled.")

# ==== TEST TELEGRAM CONNECTION ====
def test_telegram_connection():
    """Test if Telegram bot credentials are working"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            logger.info("✅ Telegram bot connection successful: @%s", bot_info['result'].get('username', 'unknown'))
            return True
        else:
            logger.error("❌ Telegram bot connection failed. Status: %d", response.status_code)
            logger.error("Response: %s", response.text)
            return False
    except Exception as e:
        logger.error("❌ Error testing Telegram connection: %s", e)
        return False

# Test connection at startup
telegram_working = test_telegram_connection()

# ==== HELPERS ====

def read_news_file():
    """Read the entire content of processed_stock_news.txt or return a default message."""
    if not os.path.exists(NEWS_FILE):
        logger.warning("News file %s not found.", NEWS_FILE)
        return "No news titles available from the provided file."
    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        logger.info("Loaded news content from %s (%d characters)", NEWS_FILE, len(content))
        return content or "No news titles available from the provided file."
    except Exception as e:
        logger.error("Error reading news file: %s", e)
        return f"Error reading news file: {e}"

def send_to_telegram(text, chat_id=None, bot_token=None):
    """Send a text message to Telegram, with enhanced error handling."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    bot_token = bot_token or TELEGRAM_BOT_TOKEN
    
    if not bot_token or not chat_id:
        logger.error("Missing bot_token or chat_id for Telegram")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        resp = requests.post(url, data=payload, timeout=30)
        
        if resp.status_code == 200:
            logger.info("✅ Message sent to Telegram successfully")
            return True
        elif resp.status_code == 404:
            logger.error("❌ Telegram 404: Invalid bot token or chat ID")
        elif resp.status_code == 403:
            logger.error("❌ Telegram 403: Bot blocked or no permission")
        elif resp.status_code == 400:
            logger.error("❌ Telegram 400: Bad request - check message format")
        else:
            logger.error("❌ Telegram error (%d): %s", resp.status_code, resp.text)
        
        logger.debug("URL: %s", url)
        return False
        
    except requests.exceptions.Timeout:
        logger.error("❌ Telegram request timeout")
        return False
    except requests.exceptions.RequestException as e:
        logger.error("❌ Telegram request error: %s", e)
        return False
    except Exception as e:
        logger.error("❌ Unexpected error sending to Telegram: %s", e)
        return False

def send_file_to_telegram(file_path, chat_id=None, bot_token=None):
    """Send a local file to Telegram as a document."""
    chat_id = chat_id or TELEGRAM_CHAT_ID
    bot_token = bot_token or TELEGRAM_BOT_TOKEN
    
    if not bot_token or not chat_id:
        logger.error("Missing bot_token or chat_id for file upload")
        return False
    
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    
    try:
        with open(file_path, "rb") as doc:
            files = {"document": doc}
            data = {"chat_id": chat_id}
            resp = requests.post(url, files=files, data=data, timeout=30)
        
        if resp.status_code == 200:
            logger.info("✅ File sent to Telegram successfully")
            return True
        else:
            logger.error("❌ Failed to send file to Telegram (%d): %s", resp.status_code, resp.text)
            return False
            
    except Exception as e:
        logger.error("❌ Error sending file to Telegram: %s", e)
        return False

def save_and_send_report(body_text):
    """Save the generated text to a dated .txt, then send a summary + the file."""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"corporate_news_{today}.txt"
    path = os.path.join(OUTPUT_DIR, filename)

    # Build content
    content = (
        "=== Indian Corporate News Analysis ===\n\n"
        f"**Analysis Results**\n{body_text}\n\n"
        f"Generated on: {today}\n"
    )
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Report saved to %s", path)
    except Exception as e:
        logger.error("Failed to write report: %s", e)
        return False

    if not telegram_working:
        logger.error("Telegram connection not working, cannot send report")
        return False

    # Send summary message
    summary = (
        "📊 *Corporate News Analysis Report*\n\n"
        f"📅 Date: {today}\n\n"
        "📋 Report generated and ready for review!"
    )
    
    success = send_to_telegram(summary)
    
    # Send file
    if not send_file_to_telegram(path):
        success = False
        # Fallback: send content as text if short enough
        if len(content) <= 4000:
            logger.info("Sending report content as text message...")
            send_to_telegram(f"```\n{content}\n```")
    
    return success

# ==== MAIN LOGIC ====

def main():
    """Main function with comprehensive error handling"""
    logger.info("Starting Corporate News Analysis...")
    
    # Check Telegram connection
    if not telegram_working:
        logger.error("Telegram connection failed. Cannot proceed.")
        return
    
    # Test with a simple message first
    test_message = "🧪 Test: Corporate News Analysis Bot Starting..."
    if not send_to_telegram(test_message):
        logger.error("Failed to send test message. Check credentials.")
        return
    
    # Handle Gemini API
    if not client:
        error_msg = "Gemini client not initialized. News analysis will be skipped."
        logger.error(error_msg)
        send_to_telegram(f"❌ *Error*\n\n{error_msg}")
        
        # Send a basic report without Gemini analysis
        news_content = read_news_file()
        basic_report = f"Raw news data (Gemini analysis unavailable):\n\n{news_content[:2000]}..."
        save_and_send_report(basic_report)
        return

    # Read news and analyze
    prompt = read_news_file()
    logger.info("Querying Gemini for analysis… (Content length: %d chars)", len(prompt))
    
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
        
        # Assemble the answer
        parts = resp.candidates[0].content.parts
        text = ""
        for p in parts:
            if not p.text:
                continue
            tag = "Thought summary:" if p.thought else "Answer:"
            text += f"{tag}\n{p.text}\n\n"

        if text.strip():
            if save_and_send_report(text):
                logger.info("✅ Report generated and sent successfully.")
            else:
                logger.error("❌ Failed to save or send report.")
        else:
            logger.error("❌ Empty response from Gemini API")
            send_to_telegram("❌ *Error*\n\nReceived empty response from Gemini API")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {e}"
        logger.error(error_msg)
        send_to_telegram(f"❌ *Error*\n\n{error_msg}")

if __name__ == "__main__":
    main()
