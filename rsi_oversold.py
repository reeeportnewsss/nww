import requests
from lxml import html
import time
import json
import os
from datetime import datetime
import pytz

BOT_TOKEN = 
CHAT_ID = "1486785506"

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

# To keep track of sent stocks - persist on disk
SENT_FILE = "sent_rsi_stocks.json"

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

def fetch_rsi_stocks():
    r = requests.get("https://www.screener.in/screens/985942/rsi-oversold-stocks/", headers=HEADERS)
    tree = html.fromstring(r.content)

    # Get all table rows (skip header row)
    stock_rows = tree.xpath('//table/tbody/tr')

    results = []
    for row in stock_rows:
        try:
            # Skip header row and empty rows
            if row.xpath('.//th'):
                continue

            # Extract all td elements
            tds = row.xpath('.//td')
            if len(tds) < 2:  # Need at least rank and company columns
                continue

            # Extract rank (first column)
            rank = tds[0].text_content().strip().replace('.', '') if tds[0].text_content() else ""

            # Extract company name and link from second column
            company_link = tds[1].xpath('.//a')
            if not company_link:
                continue

            company_name = company_link[0].text_content().strip()
            company_url = "https://www.screener.in" + company_link[0].get('href', '')

            # Extract numerical data from remaining columns (handle missing columns gracefully)
            current_price = tds[2].text_content().strip() if len(tds) > 2 else "N/A"
            high_52w = tds[3].text_content().strip() if len(tds) > 3 else "N/A"
            low_52w = tds[4].text_content().strip() if len(tds) > 4 else "N/A"
            dividend_yield = tds[5].text_content().strip() if len(tds) > 5 else "N/A"
            pb_ratio = tds[6].text_content().strip() if len(tds) > 6 else "N/A"
            market_cap = tds[7].text_content().strip() if len(tds) > 7 else "N/A"
            pe_ratio = tds[8].text_content().strip() if len(tds) > 8 else "N/A"
            roe = tds[9].text_content().strip() if len(tds) > 9 else "N/A"
            rsi = tds[10].text_content().strip() if len(tds) > 10 else "N/A"
            price_change = tds[11].text_content().strip() if len(tds) > 11 else "N/A"

            # Create unique id for stock entry (using date to reset daily)
            today = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d')
            unique_id = f"{company_name}_{today}"

            results.append({
                "rank": rank,
                "company": company_name,
                "company_url": company_url,
                "current_price": current_price,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "dividend_yield": dividend_yield,
                "pb_ratio": pb_ratio,
                "market_cap": market_cap,
                "pe_ratio": pe_ratio,
                "roe": roe,
                "rsi": rsi,
                "price_change": price_change,
                "id": unique_id
            })
        except Exception as e:
            print(f"Error parsing stock row: {e}")
            continue

    return results

def send_all_stocks_summary(stocks):
    """Send a summary message with all stocks"""
    if not stocks:
        return

    # Create summary message
    summary = f"📊 <b>RSI Oversold Stocks Summary</b>\n"
    summary += f"📅 Date: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y')}\n"
    summary += f"🔢 Total Stocks: {len(stocks)}\n\n"

    for i, stock in enumerate(stocks[:20], 1):  # Limit to 20 stocks per message due to Telegram limits
        summary += f"{i}. <b>{stock['company']}</b> - RSI: {stock['rsi']}, Price: ₹{stock['current_price']}\n"

    if len(stocks) > 20:
        summary += f"\n... and {len(stocks) - 20} more stocks"

    send_telegram_message(summary)

def main():
    sent = load_sent()

    try:
        stocks = fetch_rsi_stocks()
        print(f"Found {len(stocks)} RSI oversold stocks")

        # Send summary of all stocks
        send_all_stocks_summary(stocks)

        for stock in stocks:
            if stock["id"] not in sent:
                # Format message for RSI oversold stock
                message = (
                    f"🔴 <b>RSI Oversold Alert</b>\n\n"
                    f"<b>Company:</b> {stock['company']}\n"
                    f"<b>Rank:</b> #{stock['rank']}\n"
                    f"<b>Current Price:</b> ₹{stock['current_price']}\n"
                    f"<b>RSI:</b> {stock['rsi']}\n"
                    f"<b>Price Change:</b> {stock['price_change']}%\n"
                    f"<b>52W High/Low:</b> ₹{stock['high_52w']} / ₹{stock['low_52w']}\n"
                    f"<b>PE Ratio:</b> {stock['pe_ratio']}\n"
                    f"<b>PB Ratio:</b> {stock['pb_ratio']}\n"
                    f"<b>ROE:</b> {stock['roe']}%\n"
                    f"<b>Market Cap:</b> ₹{stock['market_cap']} Cr\n"
                    f"<b>Dividend Yield:</b> {stock['dividend_yield']}%\n\n"
                    f"<a href='{stock['company_url']}'>View Company Details</a>"
                )

                sent_ok = send_telegram_message(message)
                if sent_ok:
                    print(f"Sent RSI alert for: {stock['company']} (RSI: {stock['rsi']})")
                    sent.add(stock["id"])
                    save_sent(sent)
                    time.sleep(2)  # Small delay between messages
                else:
                    print(f"Failed to send telegram message for {stock['company']}")

    except Exception as e:
        print(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
