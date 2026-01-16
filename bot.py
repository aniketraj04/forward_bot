import asyncio
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "7244754211:AAGLxPr5R73tKSTZh6KTCaOwaKr_BYdefC8"


db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",   
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

#button

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="set forwarding rules", callback_data="set_rules")]
    ])

def rules_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text= " ADD SOURCE", callback_data="add_source")],
        [InlineKeyboardButton(text= " ADD DESTINATION", callback_data="add_destination")]
    ])


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    uid = user.id
    name = user.first_name
    username = user.username

    existing = get_user(uid)

    if existing:
        text= f"wapas aagaya badhwe, {name} 😄"
    else:
        save_user(uid, name, username)
        text=f"loru, {name}! teri sari infomation save karli maine."

    await message.answer(
        text + "\n\nChoose an option:",
        reply_markup=main_menu()
    )    


#button handler
@dp.callback_query()
async def button_handler(call: types.CallbackQuery):
    if call.data == "set_rules":
        await call.message.answer(
            "Now set your forwarding rules:",
            reply_markup=rules_menu()
        )

    elif call.data == "add_source":
        await call.message.answer("Send me the SOURCE channel ID or username.")

    elif call.data == "add_destination":
        await call.message.answer("Send me the DESTINATION channel ID or username.")

    await call.answer()

###########

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
