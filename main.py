from telegram.ext import Application, MessageHandler, filters, CommandHandler
import google.generativeai as genai
import fitz  # PyMuPDF
import os
from pymongo import MongoClient
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Set your tokens from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")  # Set your MongoDB URI in environment variables
client = MongoClient(MONGO_URI)
db = client["askmyfile_db"]  # Database name
questions_col = db["questions"]  # Collection name

# Save uploaded file
async def handle_file(update, context):
    doc = update.message.document
    file = await doc.get_file()
    file_path = f"{doc.file_name}"
    await file.download_to_drive(file_path)

    text = extract_text(file_path)
    os.remove(file_path)

    await update.message.reply_text("File uploaded! You can now ask questions.")

    context.user_data["file_text"] = text

# Extract text
def extract_text(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    else:
        return "Only PDF supported for now."

# Handle questions
async def ask(update, context):
    user_question = update.message.text
    file_text = context.user_data.get("file_text", "")

    # Upsert user document and append question to prompts list
    questions_col.update_one(
        {"user_id": update.effective_user.id},
        {
            "$set": {
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "full_name": update.effective_user.full_name,
            },
            "$push": {
                "prompts": {
                    "question": user_question,
                    "timestamp": datetime.utcnow()
                }
            }
        },
        upsert=True
    )

    if not file_text:
        await update.message.reply_text("Please upload a file first.")
        return

    prompt = f"Answer this question based on the document:\n\nDocument:\n{file_text[:4000]}\n\nQuestion:\n{user_question}"
    response = model.generate_content(prompt)
    await update.message.reply_text(response.text)

# Start command
async def start(update, context):
    await update.message.reply_text(
        "Welcome! I'm Bhanu Teja's AskMyFileBot. Please upload a PDF file. I can answer questions using only the information found in your uploaded document."
    )
    await update.message.reply_text(
        "After uploading, ask questions that can be answered from the file's content. I will only use the data in your PDF to reply."
    )

# Health check HTTP server for deployment environments
def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, format, *args):
            return  # Silence HTTP server logs

    httpd = HTTPServer(("0.0.0.0", port), HealthHandler)
    httpd.serve_forever()

# Run the bot
def main():
    # Start HTTP health check server in background thread
    threading.Thread(target=run_health_check_server, daemon=True).start()

    async def remove_webhook(app):
        await app.bot.delete_webhook(drop_pending_updates=True)

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(remove_webhook).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask))

    app.run_polling()

if __name__ == "__main__":
    main()