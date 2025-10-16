import asyncio
import os
import re
import tempfile
import fitz  # PyMuPDF
from telegram import Update
from telegram.error import RetryAfter, BadRequest
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ===========================
#   BOT TOKEN
# ===========================
BOT_TOKEN = "8229155473:AAF2MIDyGBWuIvzvw_B2G3mmIrbIrPDTLm0"  # <--- Add your real bot token here


# ===========================
#   SAFE POLL FUNCTION
# ===========================
async def send_safe_poll(context, chat_id, question_text, options, correct_option=None):
    """Safely send Telegram quiz polls with retries and rate-limit handling."""
    if len(question_text) > 300:
        question_text = question_text[:297] + "..."

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=options,
            is_anonymous=False,
            type="quiz",
            correct_option_id=correct_option,
        )
        await asyncio.sleep(0.3)

    except RetryAfter as e:
        print(f"⏳ Flood control: waiting {e.retry_after}s...")
        await asyncio.sleep(e.retry_after)
        await send_safe_poll(context, chat_id, question_text, options, correct_option)

    except BadRequest as e:
        print(f"⚠️ BadRequest: {e}")
        if "must not exceed 300" in str(e):
            question_text = question_text[:297] + "..."
            await send_safe_poll(context, chat_id, question_text, options, correct_option)
        else:
            print("⚠️ Skipped problematic question.")

    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")


# ===========================
#   EXTRACT MCQS FROM PDF
# ===========================
def extract_mcqs_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join([p.get_text("text") for p in doc])

    # Flexible pattern for questions, options (A–D), and answer letter
    pattern = (
        r"(\d+\..*?)"                # Question (starts with number)
        r"(?:A\.\s*(.*?))"           # Option A
        r"(?:B\.\s*(.*?))"           # Option B
        r"(?:C\.\s*(.*?))"           # Option C
        r"(?:D\.\s*(.*?))"           # Option D
        r"(?:Ans[:\- ]*\s*([A-Da-d]))"  # Answer letter
    )

    matches = re.findall(pattern, text, re.DOTALL)
    mcqs = []

    for q in matches:
        question = q[0].strip()
        options = [opt.strip() for opt in q[1:5]]
        answer_letter = q[5].strip().upper() if len(q) > 5 else "A"
        correct_index = "ABCD".index(answer_letter) if answer_letter in "ABCD" else 0

        mcqs.append({
            "question": question,
            "options": options,
            "correct_index": correct_index,
        })

    print(f"✅ Extracted {len(mcqs)} MCQs")
    return mcqs


# ===========================
#   PDF HANDLER FUNCTION
# ===========================
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("📥 Downloading your PDF, please wait...")

    # Download PDF file temporarily
    file = await context.bot.get_file(update.message.document.file_id)
    tmp = tempfile.mktemp(suffix=".pdf")
    await file.download_to_drive(tmp)

    # Extract MCQs
    mcqs = extract_mcqs_from_pdf(tmp)
    os.remove(tmp)

    await msg.edit_text(f"✅ Extracted {len(mcqs)} questions! Sending polls...")
    last_topic = None

    for q in mcqs:
        # 1️⃣ Optional topic line (you can show every time)
        current_topic = q.get("topic", "General")
        if True:  # Always show topic
            await context.bot.send_message(
                chat_id,
                f"📘 *Topic:* {current_topic}",
                parse_mode="Markdown",
            )
            await asyncio.sleep(0.2)

        # 2️⃣ Send quiz poll
        await send_safe_poll(
            context,
            chat_id,
            question_text=q["question"],
            options=q["options"],
            correct_option=q["correct_index"],
        )

        await asyncio.sleep(0.3)

    await context.bot.send_message(chat_id, "✅ All questions sent successfully!")


# ===========================
#   TELEGRAM APP SETUP
# ===========================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))


# ===========================
#   KEEP-ALIVE HTTP SERVER (for Render)
# ===========================
PORT = int(os.environ.get("PORT", 10000))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

# Run small HTTP server in background (Render keep-alive)
threading.Thread(
    target=lambda: HTTPServer(("", PORT), Handler).serve_forever(),
    daemon=True,
).start()

# Run the Telegram bot polling
app.run_polling()
