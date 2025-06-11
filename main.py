from telegram.ext import Application, MessageHandler, filters, CommandHandler
import google.generativeai as genai
import fitz  # PyMuPDF
import os

# Set your tokens from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

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

    if not file_text:
        await update.message.reply_text("Please upload a file first.")
        return

    prompt = f"Answer this question based on the document:\n\nDocument:\n{file_text[:4000]}\n\nQuestion:\n{user_question}"
    response = model.generate_content(prompt)
    await update.message.reply_text(response.text)

# Start command
async def start(update, context):
    await update.message.reply_text("Send me a PDF and ask me anything from it!")

# Run the bot
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask))
    app.run_polling()

if __name__ == "__main__":
    main()
