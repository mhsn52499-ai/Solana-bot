import os
import threading
import requests
import re
import time
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- سيرفر وهمي لإرضاء منصة Render ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

# --- بيانات البوت والمفاتيح ---
TELEGRAM_TOKEN = "8876813204:AAFPDXKUyMAtFITyHGuWKLHI6QA2Mx7sfcs"
GEMINI_API_KEY = "AQ.Ab8RN6IXAvonufn_46REm088uYzw7SKxBBOlujMQXrHXWqUj4g"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def check_rugcheck(mint_address):
    """فحص أمان العقد عبر RugCheck"""
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            score = data.get("score", 0)
            status = "آمن نسبياً" if score < 2000 else "مخاطرة عالية (Rug Risk)"
            return status, score
    except Exception:
        pass
    return "غير معروف", 9999

def analyze_with_gemini(coin_data):
    """التحليل المفصل المباشر عبر Gemini API مع دعم كامل لمفاتيح AQ"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""
    أنت خبير ومحلل محترف لعملات الميم على شبكة سولانا.
    حلل البيانات التالية لهذه العملة واكتب تقريراً مفصلاً ومباشراً بدون مقدمات أو تنسيقات معقدة:

    - اسم العملة: {coin_data['name']} ({coin_data['symbol']})
    - السعر الحالي: ${coin_data['price']}
    - الماركت كاب: ${coin_data['mcap']:,.2f}
    - السيولة: ${coin_data['liquidity']:,.2f}
    - حجم التداول (24h): ${coin_data['volume']:,.2f}
    - سكور الأمان: {coin_data['score']} ({coin_data['safety']})

    المطلوب بالتحديد:
    1. تقييم حجم التداول، السيولة، والماركت كاب (نسبة السيولة للماركت كاب وتأثيرها على الانزلاق السعري).
    2. نصيحة صريحة ومفصلة للمتداول (فرص الدخول المضاربي، مستويات الخطورة، وإدارة رأس المال).
    """

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    last_error = ""
    for attempt in range(2):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                result = res.json()
                text_response = result['candidates'][0]['content']['parts'][0]['text']
                clean_text = re.sub(r'[*_`#]', '', text_response)
                return clean_text
            else:
                last_error = f"HTTP {res.status_code}: {res.text[:300]}"
                print(f"[Gemini Error] {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"[Gemini Exception] {last_error}")
            time.sleep(1)

    return f"⚠️ تعذر جلب التحليل المفصل حالياً.\nتفاصيل تقنية: {last_error}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك 👋\n"
        "أرسل لي عنوان عقد (mint address) لأي عملة ميم على شبكة سولانا وراح أحللها لك بالتفصيل."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if len(text) >= 32 and " " not in text:
        await update.message.reply_text("🔎 جاري جلب وتحليل البيانات مفصلاً عبر الذكاء الاصطناعي...")

        try:
            dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{text}"
            res = requests.get(dex_url, headers=HEADERS, timeout=10)
            
            if res.status_code != 200 or not res.text.strip():
                await update.message.reply_text("❌ لم يتم استجابة المنصة بشكل صحيح، حاول مجدداً بعد قليل.")
                return

            res_json = res.json()
            pairs = res_json.get("pairs", [])

            if not pairs:
                await update.message.reply_text("❌ لم يتم العثور على بيانات لهذا العقد على DexScreener.")
                return

            pair = pairs[0]
            safety_status, score = check_rugcheck(text)

            coin_data = {
                "name": pair.get("baseToken", {}).get("name", "N/A"),
                "symbol": pair.get("baseToken", {}).get("symbol", "N/A"),
                "price": pair.get("priceUsd", "0"),
                "mcap": pair.get("marketCap", 0) or pair.get("fdv", 0),
                "liquidity": pair.get("liquidity", {}).get("usd", 0),
                "volume": pair.get("volume", {}).get("h24", 0),
                "safety": safety_status,
                "score": score
            }

            ai_analysis = analyze_with_gemini(coin_data)

            report = (
                f"🚨 تحليل العملة: {coin_data['name']} ({coin_data['symbol']}) 🚨\n\n"
                f"💵 السعر: ${coin_data['price']}\n"
                f"🧢 Market Cap: ${coin_data['mcap']:,.2f}\n"
                f"💧 السيولة: ${coin_data['liquidity']:,.2f}\n"
                f"📊 التداول (24h): ${coin_data['volume']:,.2f}\n"
                f"🛡️ الأمان: {coin_data['safety']} (سكور: {coin_data['score']})\n\n"
                f"🧠 رأي الذكاء الاصطناعي:\n{ai_analysis}\n\n"
                f"🔗 DexScreener: {pair.get('url', '')}\n"
                f"🔍 بحث X: https://x.com/search?q={coin_data['symbol']}"
            )

            await update.message.reply_text(report, disable_web_page_preview=True)

        except Exception as e:
            await update.message.reply_text(f"⚠️ حدث خطأ تقني: {str(e)}")
    else:
        await update.message.reply_text("أهلاً بك! أرسل لي عقد عملة سولانا للفحص.")

if __name__ == '__main__':
    # تشغيل السيرفر الوهمي في Thread منفصل
    t = threading.Thread(target=run_web)
    t.start()
    
    # تشغيل البوت
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
