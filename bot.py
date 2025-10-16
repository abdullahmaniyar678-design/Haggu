import asyncio
from telegram.error import RetryAfter, BadRequest

# ---------- SAFE POLL FUNCTION ----------
async def send_safe_poll(context, chat_id, question_text, options, correct_option=None):
    """
    Safely sends a Telegram poll with:
      - Auto trimming long questions
      - Auto retrying after rate limits
      - Delay between polls
    """

    # 1️⃣ Trim questions if longer than 300 characters
    if len(question_text) > 300:
        print(f"⚠️ Question too long ({len(question_text)} chars). Trimming...")
        question_text = question_text[:297] + "..."

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=options,
            is_anonymous=False,
            type='quiz',
            correct_option_id=correct_option,
        )

        # Wait a bit to respect Telegram’s rate limit (30 msgs/sec)
        await asyncio.sleep(0.3)

    except RetryAfter as e:
        print(f"⏳ Flood control: waiting {e.retry_after} seconds...")
        await asyncio.sleep(e.retry_after)
        await send_safe_poll(context, chat_id, question_text, options, correct_option)

    except BadRequest as e:
        print(f"❌ BadRequest: {e}")
        if "must not exceed 300" in str(e):
            question_text = question_text[:297] + "..."
            await send_safe_poll(context, chat_id, question_text, options, correct_option)
        else:
            print("⚠️ Skipped problematic question.")

    except Exception as e:
        print(f"⚠️ Unexpected error while sending poll: {e}")
# ---------- END OF SAFE POLL FUNCTION ----------
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import fitz, re, os, tempfile

BOT_TOKEN = "8229155473:AAF2MIDyGBWuIvzvw_B2G3mmIrbIrPDTLm0"

def extract_mcqs_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join([p.get_text("text") for p in doc])
    pattern = r"(\d+\..*?)(A\..*?)(B\..*?)(C\..*?)(D\..*?)(Ans[:\- ]?.*?)\n"
    matches = re.findall(pattern, text, re.DOTALL)
    mcqs = []
    for q in matches:
        question = q[0].strip()
        options = [q[1][2:].strip(), q[2][2:].strip(), q[3][2:].strip(), q[4][2:].strip()]
        answer = q[5].replace("Ans:", "").strip().upper()
        correct_index = "ABCD".index(answer[0]) if answer and answer[0] in "ABCD" else 0
        mcqs.append({"question": question, "options": options, "correct_index": correct_index})
    return mcqs

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("📥 Downloading your PDF, please wait...")
    file = await context.bot.get_file(update.message.document.file_id)
    tmp = tempfile.mktemp(suffix=".pdf")
    await file.download_to_drive(tmp)

    mcqs = extract_mcqs_from_pdf(tmp)
    os.remove(tmp)
    await msg.edit_text(f"✅ Extracted {len(mcqs)} questions! Sending polls...")
    chat_id = update.effective_chat.id
    last_topic = None  # to remember last topic name

for q in mcqs:
    # 1️⃣ Show topic name once
    current_topic = q.get("topic", "General")  # default "General" if no topic
    if current_topic != last_topic:
        await context.bot.send_message(
            chat_id,
            f"📘 *Topic:* {current_topic}",
            parse_mode="Markdown"
        )
        last_topic = current_topic  # remember topic
        await asyncio.sleep(0.3)

    # 2️⃣ Send question image(s) (if any)
    if "question_images" in q and q["question_images"]:
        for img in q["question_images"]:
            await context.bot.send_photo(chat_id, img)
            await asyncio.sleep(0.3)

    # 3️⃣ Send the question as a poll
    await send_safe_poll(
        context,
        chat_id,
        question_text=q["question"],
        options=q["options"],
        correct_option=q["correct_index"]
    )

    # 4️⃣ Send hidden (grey) explanation
    if "explanation" in q and q["explanation"]:
        await asyncio.sleep(1)
        text = q["explanation"]

        # Escape special characters so Markdown doesn't break
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for ch in special_chars:
            text = text.replace(ch, f"\\{ch}")

        await context.bot.send_message(
            chat_id,
            f"💡 *Explanation:* ||{text}||",
            parse_mode="MarkdownV2"
        )

    # 5️⃣ Send explanation images (if any)
    if "explanation_images" in q and q["explanation_images"]:
        for img in q["explanation_images"]:
            await context.bot.send_photo(chat_id, img)
            await asyncio.sleep(0.3)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

app.run_polling()
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 10000))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
        
# Start a background server
import threading
threading.Thread(target=lambda: HTTPServer(("", PORT), Handler).serve_forever(), daemon=True).start()

# Now your telegram bot main loop
bot.infinity_polling()









