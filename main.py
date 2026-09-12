import os
import logging
from telegram import Update, PollAnswer
from telegram.ext import Application, CommandHandler, ContextTypes, PollAnswerHandler
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8443))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB Setup
if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client["quiz_bot_db"]
    scores_col = db["user_scores"]  # Scores save karne ke liye collection
    print("✅ MongoDB Database Connected Successfully!")
else:
    raise ValueError("MONGO_URI nahi mila! Check your variables.")

QUIZ_QUESTIONS = [
    {
        "question": "Python ka avishkar kisne kiya tha?",
        "options": ["Dennis Ritchie", "Guido van Rossum", "James Gosling", "Bjarne Stroustrup"],
        "correct_id": 1,
        "explanation": "Guido van Rossum ne 1991 me Python ko release kiya."
    },
    {
        "question": "Telegram kis saal me launch hua tha?",
        "options": ["2010", "2013", "2015", "2018"],
        "correct_id": 1,
        "explanation": "Telegram August 2013 me launch hua tha."
    }
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Quiz shuru karne ke liye `/quiz` likhein.\nLeaderboard dekhne ke liye `/leaderboard` likhein.")

async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.chat_data['current_question'] = 0
    await send_next_question(chat_id, context)

async def send_next_question(chat_id, context: ContextTypes.DEFAULT_TYPE):
    q_index = context.chat_data.get('current_question', 0)
    
    if q_index >= len(QUIZ_QUESTIONS):
        await context.bot.send_message(chat_id=chat_id, text="🎉 Quiz khatam ho gaya! `/leaderboard` check karein.")
        return

    quiz = QUIZ_QUESTIONS[q_index]
    
    # Poll bhej rahe hain aur uski ID ko track kar rahe hain
    message = await context.bot.send_poll(
        chat_id=chat_id,
        question=quiz["question"],
        options=quiz["options"],
        type="quiz",
        correct_option_id=quiz["correct_id"],
        explanation=quiz["explanation"],
        is_anonymous=False
    )
    
    # Bot ke memory me save kar rahe hain ki is Poll ID ka sahi jawab kya hai
    context.bot_data[message.poll.id] = quiz["correct_id"]

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if 'current_question' in context.chat_data:
        context.chat_data['current_question'] += 1
        await send_next_question(chat_id, context)
    else:
        await update.message.reply_text("❌ Pehle `/quiz` shuru karein!")

# User ke jawab ko track aur save karne ka function
async def receive_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user = poll_answer.user
    
    # Pata lagao ki kya user ne sahi jawab diya hai
    correct_id = context.bot_data.get(poll_id)
    if correct_id is not None and poll_answer.option_ids == [correct_id]:
        # User ka score database me update/insert karein (+1 point)
        scores_col.update_one(
            {"user_id": user.id},
            {"$inc": {"score": 1}, "$set": {"username": user.username or user.first_name}},
            upsert=True
        )

# Leaderboard/Scorecard dikhane ka command
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Highest score wale top 10 users ko database se nikalna
    top_users = scores_col.find().sort("score", -1).limit(10)
    
    text = "🏆 **QUIZ LEADERBOARD** 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user['username']} — {user['score']} Pts\n"
        
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", send_quiz))
    application.add_handler(CommandHandler("next", next_question))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    
    # Is handler se pata chalta hai ki kisne kya option select kiya
    application.add_handler(PollAnswerHandler(receive_quiz_answer))

    if RENDER_EXTERNAL_URL:
        application.run_webhook(
            listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN,
            webhook_url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == '__main__':
    main()
  
