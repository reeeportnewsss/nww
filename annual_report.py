import requests
from lxml import html
import time
import json
import os
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "Host": "www.screener.in",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "identity",
    "Referer": "https://www.screener.in/screens/",
    "Connection": "keep-alive",
    "Cookie": "csrftoken=Cd05eytoRuKT77n18FK5HfmDh6lbOCLV; sessionid=mk124gu1ijkpit4z8ze80bam9zqpctnz",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i"
}

# To keep track of sent annual reports - persist on disk
SENT_FILE = "sent_annual_reports.json"

def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent(sent_set):
    with open(SENT_FILE, "w") as f:
        json.dump(list(sent_set), f)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    r = requests.post(url, data=payload)
    return r.ok

def fetch_annual_reports():
    r = requests.get("https://www.screener.in/annual-reports/", headers=HEADERS)
    tree = html.fromstring(r.content)

    # Get all list items using the provided XPath
    report_items = tree.xpath('/html/body/main/div[2]/div[2]/ul/li')

    results = []
    for item in report_items:
        try:
            # Extract the <a> tag for company name, fiscal year, and PDF link
            link = item.xpath('.//a')
            if not link:
                continue

            company_name = link[0].xpath('.//strong[@class="font-weight-500"]/text()')
            company_name = company_name[0].strip() if company_name else "N/A"

            fiscal_year = link[0].xpath('.//span[@class="sub font-size-14"]/text()')
            fiscal_year = fiscal_year[0].strip() if fiscal_year else "N/A"

            pdf_url = link[0].get('href', 'N/A')

            # Extract details from the div with class 'font-size-12 sub'
            details_div = item.xpath('.//div[@class="font-size-12 sub"]')
            if not details_div:
                continue

            # Extract time, market cap, sales, profit, and results link
            details_text = details_div[0].text_content().strip().split('·')
            time_posted = details_text[0].strip() if len(details_text) > 0 else "N/A"

            market_cap = "N/A"
            sales = "N/A"
            sales_change = "N/A"
            profit = "N/A"
            profit_change = "N/A"
            results_url = "N/A"

            for detail in details_text:
                detail = detail.strip()
                if "Market Cap" in detail:
                    market_cap = detail.split(':')[1].strip() if ':' in detail else "N/A"
                elif "Sales" in detail:
                    sales = detail.split('Cr')[0].strip() + "Cr" if 'Cr' in detail else "N/A"
                    # Extract sales change if present
                    sales_change_elem = details_div[0].xpath('.//span[contains(@class, "change") and contains(text(), "⇡") or contains(text(), "⇣")]')
                    sales_change = sales_change_elem[0].text_content().strip() if sales_change_elem else "N/A"
                elif "Profit" in detail:
                    profit = detail.split('Cr')[0].strip() + "Cr" if 'Cr' in detail else "N/A"
                    # Extract profit change if present
                    profit_change_elem = details_div[0].xpath('.//span[contains(@class, "change") and contains(text(), "⇡") or contains(text(), "⇣")]')
                    profit_change = profit_change_elem[1].text_content().strip() if len(profit_change_elem) > 1 else "N/A"

            # Extract results link
            results_link = details_div[0].xpath('.//a[@href and contains(text(), "Results")]')
            results_url = "https://www.screener.in" + results_link[0].get('href', '') if results_link else "N/A"

            # Create unique ID for the report entry (using company name and date)
            today = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d')
            unique_id = f"{company_name}_{today}"

            results.append({
                "company": company_name,
                "fiscal_year": fiscal_year,
                "pdf_url": pdf_url,
                "time_posted": time_posted,
                "market_cap": market_cap,
                "sales": sales,
                "sales_change": sales_change,
                "profit": profit,
                "profit_change": profit_change,
                "results_url": results_url,
                "id": unique_id
            })
        except Exception as e:
            print(f"Error parsing annual report item: {e}")
            continue

    return results

def send_all_reports_summary(reports):
    """Send a summary message with all annual reports"""
    if not reports:
        return

    # Create summary message
    summary = f"📊 <b>Annual Reports Summary</b>\n"
    summary += f"📅 Date: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y')}\n"
    summary += f"🔢 Total Reports: {len(reports)}\n\n"

    for i, report in enumerate(reports[:20], 1):  # Limit to 20 reports per message due to Telegram limits
        summary += f"{i}. <b>{report['company']}</b> - {report['fiscal_year']}, Market Cap: {report['market_cap']}\n"

    if len(reports) > 20:
        summary += f"\n... and {len(reports) - 20} more reports"

    send_telegram_message(summary)

def main():
    sent = load_sent()

    try:
        reports = fetch_annual_reports()
        print(f"Found {len(reports)} annual reports")

        # Send summary of all reports
        send_all_reports_summary(reports)

        for report in reports:
            if report["id"] not in sent:
                # Format message for annual report
                message = (
                    f"📄 <b>Annual Report Alert</b>\n\n"
                    f"<b>Company:</b> {report['company']}\n"
                    f"<b>Fiscal Year:</b> {report['fiscal_year']}\n"
                    f"<b>Time Posted:</b> {report['time_posted']}\n"
                    f"<b>Market Cap:</b> {report['market_cap']}\n"
                    f"<b>Sales:</b> {report['sales']} <b>({report['sales_change']})</b>\n"
                    f"<b>Profit:</b> {report['profit']} <b>({report['profit_change']})</b>\n\n"
                    f"<a href='{report['pdf_url']}'>View Annual Report PDF</a>\n"
                    f"<a href='{report['results_url']}'>View Financial Results</a>"
                )

                sent_ok = send_telegram_message(message)
                if sent_ok:
                    print(f"Sent annual report alert for: {report['company']} ({report['fiscal_year']})")
                    sent.add(report["id"])
                    save_sent(sent)
                    time.sleep(2)  # Small delay between messages
                else:
                    print(f"Failed to send telegram message for {report['company']}")

    except Exception as e:
        print(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
