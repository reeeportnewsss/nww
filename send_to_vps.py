import os
import logging
import requests
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime

# ==== CONFIGURATION ====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_FILE = "processed_stock_news.txt"  # Path to news file
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/tmp')  # Local temp directory in GitHub Actions

# === Telegram Bot Config ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Channel ID or user ID

# Ensure the local output directory exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gemini_file.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set your Gemini API key
os.environ['GOOGLE_API_KEY'] = GEMINI_API_KEY

try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None

MODEL_ID = "gemini-2.5-flash-preview-05-20"

# Read news file content
def read_news_file():
    """
    Read the entire content of processed_stock_news.txt as a string.
    Returns:
        str: File content or error message if file not found.
    """
    try:
        if os.path.exists(NEWS_FILE):
            with open(NEWS_FILE, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            logger.info(f"Loaded news content from {NEWS_FILE}")
            return content if content else "No news titles available from the provided file."
        else:
            logger.warning(f"News file {NEWS_FILE} not found.")
            return "No news titles available from the provided file."
    except Exception as e:
        logger.error(f"Error reading news file: {e}")
        return f"Error reading news file: {str(e)}"

def send_to_telegram(message, chat_id=TELEGRAM_CHAT_ID, bot_token=TELEGRAM_BOT_TOKEN):
    """
    Send a message to Telegram bot.
    Args:
        message (str): Message to send
        chat_id (str): Telegram chat ID
        bot_token (str): Telegram bot token
    Returns:
        bool: True if message sent successfully, False otherwise.
    """
    try:
        # Telegram API URL
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Message data
        data = {
            'chat_id': chat_id,
            'text': message,
           # Enable markdown formatting
        }
        
        # Send POST request
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            logger.info("Message sent to Telegram successfully")
            return True
        else:
            logger.error(f"Failed to send message to Telegram. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {e}")
        return False

def send_file_to_telegram(file_path, chat_id=TELEGRAM_CHAT_ID, bot_token=TELEGRAM_BOT_TOKEN):
    """
    Send a file to Telegram bot.
    Args:
        file_path (str): Path to the file to send
        chat_id (str): Telegram chat ID
        bot_token (str): Telegram bot token
    Returns:
        bool: True if file sent successfully, False otherwise.
    """
    try:
        # Telegram API URL for sending documents
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        
        # Prepare file and data
        with open(file_path, 'rb') as file:
            files = {'document': file}
            data = {'chat_id': chat_id}
            
            # Send POST request
            response = requests.post(url, files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            logger.info("File sent to Telegram successfully")
            return True
        else:
            logger.error(f"Failed to send file to Telegram. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending file to Telegram: {e}")
        return False

def save_and_send_report(response_text):
    """
    Save the Gemini response to a .txt file locally and send it to Telegram.
    Args:
        response_text (str): Response from news file analysis or error message.
    Returns:
        bool: True if file saved and sent successfully, False otherwise.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create file content
    file_content = f"=== Indian Corporate News Analysis ===\n\n"
    file_content += f"**Best News Item from File**\n{response_text}\n\n"
    file_content += f"Generated on: {today}"

    # Generate file name with date
    file_name = f"corporate_news_{today}.txt"
    local_file_path = os.path.join(OUTPUT_DIR, file_name)

    # Save to local file
    try:
        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        logger.info(f"File saved locally to {local_file_path}")
    except Exception as e:
        logger.error(f"Failed to save local file: {e}")
        return False

    # Send both message and file to Telegram
    success = True
    
    # First, send a summary message
    summary_message = f"📊 *Corporate News Analysis Report*\n\n"
    summary_message += f"📅 Date: {today}\n\n"
    summary_message += f"📋 Report generated and ready for review!"
    
    if not send_to_telegram(summary_message):
        success = False
    
    # Then send the full report as a file
    if not send_file_to_telegram(local_file_path):
        success = False
        # If file sending fails, try to send the content as a message
        # (Note: Telegram messages have a 4096 character limit)
        if len(file_content) <= 4000:
            logger.info("Attempting to send report content as message...")
            send_to_telegram(f"```\n{file_content}\n```")
    
    return success

# Read news file content to use as the prompt
news_prompt = read_news_file()

def main():
    """
    Main function to query Gemini API with news file content and send response to Telegram.
    """
    if not client:
        error_msg = "Failed to initialize Gemini client. Check API key and network."
        logger.error(error_msg)
        send_to_telegram(f"❌ *Error*\n\n{error_msg}")
        return

    try:
        # Query Gemini API with news file content
        logger.info("Querying Gemini API for news file analysis...")
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=news_prompt,
            config=GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=10000
                ),
                response_modalities=["TEXT"]
            )
        )

        # Extract response
        response_text = ""
        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if part.thought:
                response_text += f"Thought summary:\n{part.text}\n\n"
            else:
                response_text += f"Answer:\n{part.text}\n\n"

        # Save and send report
        if save_and_send_report(response_text):
            logger.info("Corporate news analysis report saved and sent to Telegram successfully.")
        else:
            logger.error("Failed to save or send corporate news analysis report.")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {str(e)}"
        logger.error(error_msg)
        send_to_telegram(f"❌ *Error*\n\n{error_msg}")

if __name__ == "__main__":
    main()
