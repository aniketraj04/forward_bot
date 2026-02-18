import os
import asyncio
import mysql.connector
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states import RuleState, EditRuleState 

load_dotenv()

# Railway Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

db = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQL_DATABASE"), # Changed to match Railway
    port=int(os.getenv("MYSQLPORT", 3306)),
    autocommit=True 
)

def get_cursor():
    try:
        db.ping(reconnect=True, attempts=3, delay=1)
    except:
        pass
    return db.cursor()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE FUNCTIONS ---

def get_user(user_id):
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

def save_user(user_id, first_name, username):
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s)",
        (user_id, first_name, username)
    )

def get_user_rules(user_id):
    cursor = get_cursor()
    cursor.execute(
        "SELECT id, source_chat_id, destination_chat_ids, is_active FROM rules WHERE user_id=%s",
        (user_id,)
    )
    return cursor.fetchall()

# --- UI & HANDLERS ---

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="set forwarding rules", callback_data="set_rules")],
        [InlineKeyboardButton(text="my rules", callback_data="my_rules")]
    ])

# OPTION 1 FIX: Changed WaitingForSource to Waiting_source to match your states.py
@dp.callback_query(F.data == "set_rules")
async def set_rules_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(RuleState.Waiting_source) 
    await call.message.answer("Forwarding Setup: \n\n1. Add me as admin to Source & Destination.\n2. Forward a message from the SOURCE channel here.")
    await call.answer()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    if not get_user(user.id):
        save_user(user.id, user.first_name, user.username)
    await message.answer(f"Hello {user.first_name}! Choose an option:", reply_markup=main_menu())

# (Keep your existing show_rules, edit_filters, and forward_from_source logic below)

async def main():
    # Force delete webhook to prevent ConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())