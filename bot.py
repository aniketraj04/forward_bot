import asyncio
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "7244754211:AAGLxPr5R73tKSTZh6KTCaOwaKr_BYdefC8"

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",   # your password
    database="tg_bot"
)
cursor = db.cursor()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

def save_user(user_id, first_name, username):
    cursor.execute(
        "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s)",
        (user_id, first_name, username)
    )
    db.commit()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    uid = user.id
    name = user.first_name
    username = user.username

    existing = get_user(uid)

    if existing:
        await message.answer(f"wapas aagaya badhwe, {name} 😄")
    else:
        save_user(uid, name, username)
        await message.answer(f"loru, {name}! teri sari infomation save karli maine.")

@dp.message()
async def any_message(message: types.Message):
    user = message.from_user
    uid = user.id

    if not get_user(uid):
        save_user(uid, user.first_name, user.username)
        await message.answer("You are new, I saved you in my memory 😊")
    else:
        await message.answer("I already know you 😎")

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
