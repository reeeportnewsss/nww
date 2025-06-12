import os
import re
import time
import json
from google import genai
from datetime import datetime
from itertools import cycle

# === Configuration ===
# Load API keys from GitHub environment variables
API_KEYS = [
    os.getenv('gemini_api_key1'),
    os.getenv('gemini_api_key2'),
    os.getenv('gemini_api_key3'),
    os.getenv('gemini_api_key4'),
]
# Filter out None values in case some keys are not set
API_KEYS = [key for key in API_KEYS if key]
if not API_KEYS:
    raise ValueError("No valid API keys found in environment variables")

api_key_cycle = cycle(API_KEYS)
current_api_key = next(api_key_cycle)
os.environ['GOOGLE_API_KEY'] = current_api_key
client = genai.Client()
MODEL_ID = "gemini-2.0-flash"
input_file = "valid_title.txt"
output_dir = "/root/gemini_direct/gemini_summary/response"
output_file = "combined_response.txt"
processed_file = "processed.json"
os.makedirs(output_dir, exist_ok=True)

# === Load previously processed titles ===
if os.path.exists(processed_file):
    with open(processed_file, "r", encoding="utf-8") as pf:
        processed_titles = set(json.load(pf))
else:
    processed_titles = set()

# === Read input titles ===
with open(input_file, "r", encoding="utf-8") as f:
    titles = [line.strip() for line in f if line.strip()]

# === Initialize combined response storage ===
combined_response = []

# === Process each title ===
for title in titles:
    if title in processed_titles:
        print(f"Skipping already processed title: '{title}'")
        continue
    
    max_retries = len(API_KEYS) * 2
    retry_count = 0
    success = False
    response_text = ""
    
    while retry_count < max_retries and not success:
        try:
            prompt = (
                f"Summarize the news article in detail by searching given title on web "
                f"and by reading some recent article based on website,,, title:- {title}"
            )
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config={"tools": [{"google_search": {}}]},
            )
            response_text = response.text
            print(f"Processed title '{title}'")
            processed_titles.add(title)
            success = True
        except Exception as e:
            if "401" in str(e):
                print(f"401 error for title '{title}' with API key}. Retrying...")
                retry_count += 1
                current_api_key = next(api_key_cycle)
                os.environ['GOOGLE_API_KEY'] = current_api_key
                client = genai.Client()
                time.sleep(2 ** retry_count)
            else:
                print(f"Error processing title '{title}': {str(e)}")
                break
    
    if success:
        print(f"Failed to process title '{title}' after {max_retries} attempts.")
    else:
        # Store individual response
        combined_response.append({
            "title": title,
            "summary": response_text
        })

# === Generate combined output with summary ===
with open(output_file, "w", encoding="utf-8") as f:
    f.write("=== Combined News Summaries ===\n\n")
    f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    # Write overall summary
    f.write("== Overall Summary ==\n")
    if combined_response:
        summary_text = f"Summary of {len(combined_response)} articles:\n"
        for i, entry in enumerate(combined_response, 1):
            summary_text += f"{i}. {entry['title']}: {entry['summary'][:100]}...\n"
        f.write(summary_text + "\n")
    else:
        f.write("No new articles were processed.\n\n")

    # Write detailed responses
    f.write("== Detailed Article Summaries ==\n\n")
    for entry in combined_response:
        f.write(f"Title: {entry['title']}\n")
        f.write(f"Summary:\n{entry['summary']}\n")
        f.write("-" * 80 + "\n\n")

print(f"Saved combined response to '{output_file}'")

# === Save updated processed titles ===
with open(processed_file, "w", encoding="utf-8") as pf:
    json.dump(list(processed_titles), pf, indent=2, ensure_ascii=False)
