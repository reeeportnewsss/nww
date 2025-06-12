import os
import re
import time
import json
from itertools import cycle
from google import genai
from google.genai.types import GenerateContentConfig

# === API Configuration ===
API_KEYS = [
    os.getenv('gemini_api_key1'),
    os.getenv('gemini_api_key2'),
    os.getenv('gemini_api_key3'),
    os.getenv('gemini_api_key4'),
]

api_key_cycle = cycle(API_KEYS)
current_api_key = next(api_key_cycle)
os.environ['GOOGLE_API_KEY'] = current_api_key
client = genai.Client()
MODEL_ID = "gemini-2.5-flash-preview-05-20"

# === File paths ===
title_file = "title.txt"
output_file = "valid_title.txt"

# === Filtering prompt ===
filtering_prompt = """You are an automated sentiment analysis and news filtering tool focused on brokerage-related market insights.

I will provide a plain .txt file containing a list of news headlines (one per line). Your task is to analyze each headline individually and:

Filter out irrelevant content (e.g., entertainment news, politics unrelated to markets, global stock updates with no direct India linkage).

Retain only headlines that contain market-relevant commentary or action from brokerages such as:

Buy/Sell/Hold recommendations

Target price changes

Earnings outlook or company-specific analysis

Sector outlooks or upgrades/downgrades

Macroeconomic views from brokerages (e.g., on inflation, GDP, interest rates)

Institutional flow or market strategy updates

Coverage initiations

Exclude any foreign stock views unless they are directly tied to Indian markets or sectors.

If multiple headlines have the same meaning from different sources, include only one representative version to avoid redundancy.

Your output should be a cleaned list of only the relevant brokerage-related headlines, with no greetings or summaries—the result will be used directly in an article reader pipeline.
example input:
Nomura upgrades ICICI Bank to 'Buy', raises target to ₹1,200
Shahrukh Khan launches new OTT platform
Jefferies maintains 'Hold' on Infosys, lowers target to ₹1,450
Mumbai rains cause traffic snarls in several areas
ICICI Direct sees 15% upside in L&T; retains 'Buy' rating
Nomura upgrades ICICI Bank to Buy, target ₹1,200 set

example output:
Nomura upgrades ICICI Bank to 'Buy', raises target to ₹1,200
Jefferies maintains 'Hold' on Infosys, lowers target to ₹1,450
ICICI Direct sees 15% upside in L&T; retains 'Buy' rating

so below is the content of the file you need to filter:

"""

# === Read title.txt file ===
try:
    with open(title_file, "r", encoding="utf-8") as f:
        titles_content = f.read().strip()

    # Combine prompt with title data
    full_prompt = filtering_prompt + titles_content

    # === Process with Gemini API ===
    max_retries = len(API_KEYS) * 2
    retry_count = 0
    success = False

    while retry_count < max_retries and not success:
        try:
            time.sleep(5)
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=full_prompt,
                config=GenerateContentConfig(
                    thinking_config=genai.types.ThinkingConfig(
                        include_thoughts=True,
                        thinking_budget=3500
                    ),
                    response_modalities=["TEXT"]
                )
            )

            # Save filtered titles
            with open(output_file, "w", encoding="utf-8") as out_f:
                out_f.write(response.text)

            print(f"✅ Title filtering completed. Filtered titles saved to: {output_file}")
            success = True

        except Exception as e:
            if "501" in str(e):
                print(f"⚠️  501 error with API key {current_api_key}. Switching key...")
                retry_count += 1
                current_api_key = next(api_key_cycle)
                os.environ['GOOGLE_API_KEY'] = current_api_key
                client = genai.Client()
                time.sleep(2 ** min(retry_count, 5))  # backoff
            else:
                print(f"❌ Error processing titles: {e}")
                break

    if not success:
        print("❌ Failed to process titles after all retries")

except FileNotFoundError:
    print(f"❌ Error: {title_file} not found")
except Exception as e:
    print(f"❌ Error reading file: {e}")
