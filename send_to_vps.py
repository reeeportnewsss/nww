import os
import logging
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime
import paramiko

# ==== CONFIGURATION ====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_FILE = "processed_stock_news.txt"  # Path to news file
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/')  # Local temp directory in GitHub Actions
VPS_HOST = os.getenv('VPS_HOST')  # VPS hostname or IP (e.g., 192.168.1.100)
VPS_USER = os.getenv('VPS_USER')  # VPS SSH username
VPS_PASS = os.getenv('VPS_PASS')  # VPS SSH password (or use key-based auth)
VPS_DEST_DIR = os.getenv('VPS_DEST_DIR', '/root/reports')  # Destination directory on VPS
VPS_PORT = int(os.getenv('VPS_PORT', 22))  # SSH port, default 22

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

# Read news file content to use as the prompt
today = datetime.now().strftime("%Y-%m-%d")
news_prompt = read_news_file()

def save_to_file(response_text):
    """
    Save the Gemini response to a .txt file locally and transfer it to the VPS.
    Args:
        response_text (str): Response from news file analysis or error message.
    Returns:
        bool: True if file saved and transferred successfully, False otherwise.
    """
    # Create file content
    file_content = f"=== Indian Corporate News Analysis ===\n\n"
    file_content += f"**Best News Item from File**\n{response_text}\n\n"

    # Generate file name with date
    file_name = f"corporate_news_{today}.txt"
    local_file_path = os.path.join(OUTPUT_DIR, file_name)
    remote_file_path = os.path.join(VPS_DEST_DIR, file_name)

    # Save to local file
    try:
        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        logger.info(f"File saved locally to {local_file_path}")
    except Exception as e:
        logger.error(f"Failed to save local file: {e}")
        return False

    # Transfer file to VPS using Paramiko
    try:
        # Initialize SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to VPS
        ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, password=VPS_PASS)
        
        # Initialize SFTP
        sftp = ssh.open_sftp()
        
        # Ensure remote directory exists
        try:
            sftp.stat(VPS_DEST_DIR)
        except FileNotFoundError:
            sftp.mkdir(VPS_DEST_DIR)
        
        # Transfer file
        sftp.put(local_file_path, remote_file_path)
        logger.info(f"File transferred to VPS: {remote_file_path}")
        
        # Close connections
        sftp.close()
        ssh.close()
        return True
    except Exception as e:
        logger.error(f"Failed to transfer file to VPS: {e}")
        return False

def main():
    """
    Main function to query Gemini API with news file content and save/transfer response to a file.
    """
    if not client:
        error_msg = "Failed to initialize Gemini client. Check API key and network."
        logger.error(error_msg)
        save_to_file(error_msg)
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

        # Save and transfer file
        if save_to_file(response_text):
            logger.info("Corporate news analysis report saved and transferred successfully.")
        else:
            logger.error("Failed to save or transfer corporate news analysis report.")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {str(e)}"
        logger.error(error_msg)
        save_to_file(error_msg)

if __name__ == "__main__":
    main()
