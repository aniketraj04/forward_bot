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

def save_rule(user_id, source_id, dest_id):
    try:
        cursor.execute(
            "INSERT INTO rules (user_id, source_chat_id, destination_chat_id) VALUES (%s, %s, %s)",
            (user_id, source_id, dest_id)
        )
        db.commit()
        return True
    except mysql.connector.errors.IntegrityError:
        return False

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

#source 
@dp.message(RuleState.Waiting_source)
async def get_source(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)

        if member.status not in ["administrator", "creator"]:
            await message.answer("Make me admin and send again.")
            return        

        await state.update_data(source=chat.id)
        await message.answer("Source channel saved. Now add destination channel.")


    except:
        await message.answer("Invalid channel.")


#destination_weding 
@dp.message(RuleState.Waiting_destination)
async def get_destination(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)


        if member.status not in ["administrator", "creator"]:
            await message.answer("Make me admin and send again.")
            return
        
        data = await state.get_data()
        source_id = data.get("source")

        if not source_id:
            await message.answer("First add source channel.")
            await state.clear()
            return

        ok = save_rule(message.from_user.id, source_id, chat.id)

        if not ok:
           await message.answer("❌ This channel is already added for this source.")
           await state.clear()
           return

        await message.answer("✅ Rule saved! Auto-forwarding is now active.")
        await state.clear()


    except:
        await message.answer("Invalid channel.")


@dp.channel_post()
async def forward_from_source(message: types.Message):
    source_id = message.chat.id

    cursor.execute(
        "SELECT destination_chat_id FROM rules WHERE source_chat_id = %s",
        (source_id,)
    )
    destinations = cursor.fetchall()

    for (dest_id,) in destinations:
        try:
            await message.copy_to(dest_id)
        except:
            pass


@dp.message()
async def any_message(message: types.Message):
    user = message.from_user
    uid = user.id

    if not get_user(uid):
        save_user(uid, user.first_name, user.username)
        await message.answer("You are new, I saved you in my memory 😊")
    else:
        await message.answer("I already know you ")  



async def main():
    await dp.start_polling(bot)

asyncio.run(main())