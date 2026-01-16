import asyncio
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import RuleState
from aiogram.fsm.context import FSMContext

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
async def button_handler(call: types.CallbackQuery, state: FSMContext):
    if call.data == "set_rules":
        await call.message.answer(
            "Now set your forwarding rules:",
            reply_markup=rules_menu()
        )

    elif call.data == "add_source":
        await call.message.answer("Send me the SOURCE channel ID or username.")
        await state.set_state(RuleState.Waiting_source)

    elif call.data == "add_destination":
        await call.message.answer("Send me the DESTINATION channel ID or username.")
        await state.set_state(RuleState.Waiting_destination)
    await call.answer()

###########

@dp.message(RuleState.Waiting_source)
async def get_source(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id,bot.id)
        print(member.status) 
        print(type(member.status))

        if member.status not in ["member"]:
            await message.answer("MAke me admin and send again.")
            return        

        await state.update_data(source=chat.id)
        await message.answer("source channel saved.")
        await state.clear()

    except:
        await message.answer("Invalid channel hai lodu.")


@dp.message(RuleState.Waiting_destination)
async def get_destination(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id,bot.id)

        if member.status not in["member"]:
            await message.answer(" Make me admin and send again.")
            return
        
        await state.update_data(destination=chat.id)
        await message.answer("destination channel saved.")
        await state.clear()        
    except:
        await message.answer("invalidate channel hai lodu")


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



