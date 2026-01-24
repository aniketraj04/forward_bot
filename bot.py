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

def get_user_rules(user_id):
    cursor.execute(
        "SELECT id, source_chat_id, destination_chat_ids FROM rules WHERE user_id=%s",
        (user_id,)
    )
    return cursor.fetchall()


def delete_rule(rule_id, user_id):
    cursor.execute(
        "DELETE FROM rules WHERE  id=%s AND user_id=%s",
        (rule_id, user_id)
    )
    db.commit()

def save_rule(user_id, source_id, destination_ids_str):
    try:
        cursor.execute(
            "INSERT INTO rules (user_id, source_chat_id, destination_chat_ids) VALUES (%s,%s,%s)",
            (user_id, source_id, destination_ids_str)
        )
        db.commit()
        return True
    except mysql.connector.errors.IntegrityError:
        return False

#button

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="set forwarding rules", callback_data="set_rules")],
        [InlineKeyboardButton(text="my rules", callback_data="my_rules")]
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

@dp.callback_query(lambda c: c.data == "my_rules")
async def show_rules(call: types.CallbackQuery):
    rules = get_user_rules(call.from_user.id)

    if not rules:
        await call.message.answer("You have no rules.")
        await call.answer()
        return

    kb = []

    for rid, src, dsts in rules:
        kb.append([
            InlineKeyboardButton(
                text=f"{src} → {dsts}",
                callback_data="noop"
            )
        ])
        kb.append([
        InlineKeyboardButton(
            text="Delete",
            callback_data=f"del_{rid}"
        )
    ])    

    await call.message.answer(
        "Your rules (tap to delete):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await call.answer()

@dp.callback_query(lambda c: c.data == "noop")
async def noop_handler(call: types.CallbackQuery):
    await call.answer()




@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_rule_btn(call: types.CallbackQuery):
    rule_id = int(call.data.split("_")[1])
    delete_rule(rule_id, call.from_user.id)
    await call.message.answer("❌ Rule deleted.")
    await show_rules(call)
    await call.answer()


@dp.callback_query()
async def button_handler(call: types.CallbackQuery, state: FSMContext):
    if call.data == "set_rules":
        await call.message.answer(
            "Now set your forwarding rules:",
            reply_markup=rules_menu()
        )

    elif call.data == "add_source":
        await call.message.answer("Forward a post from your SOURCE channel.")
        await state.set_state(RuleState.Waiting_source)

    elif call.data == "add_destination":
        await call.message.answer("Forward a post from DESTINATION channel (send multiple, then /done).")
        await state.set_state(RuleState.Waiting_destination)
    await call.answer()




###########

#source 
@dp.message(RuleState.Waiting_source)
async def get_source(message: types.Message, state: FSMContext):
    if message.forward_from_chat is not None:
        channel = message.forward_from_chat.id

        print(message.forward_from_chat.id)
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
    else:
        await message.answer("please forward only a post from your channel")


#destination_weding 
@dp.message(RuleState.Waiting_destination)
async def get_destination(message: types.Message, state: FSMContext):

    # FINAL SAVE
    if message.text == "/done":
        data = await state.get_data()
        source_id = data.get("source")
        destinations = data.get("destinations", [])

        if not source_id or not destinations:
            await message.answer("Source or destination missing.")
            await state.clear()
            return

        dest_string = ",".join(map(str, destinations))

        save_rule(message.from_user.id, source_id, dest_string)

        await message.answer("✅ Rule saved with multiple destinations!")
        await state.clear()
        return

    # ADD DESTINATION
    if message.forward_from_chat:
        channel = message.forward_from_chat.id

        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)

        if member.status not in ["administrator", "creator"]:
            await message.answer("Make me admin first.")
            return

        data = await state.get_data()
        destinations = data.get("destinations", [])

        if channel not in destinations:
            destinations.append(channel)
            await state.update_data(destinations=destinations)
            await message.answer("Channel added. Send more or /done")
        else:
            await message.answer("Channel already added.")
    else:
        await message.answer("Forward a channel post only.")



@dp.channel_post()
async def forward_from_source(message: types.Message):
    source_id = message.chat.id

    cursor.execute(
        "SELECT destination_chat_ids FROM rules WHERE source_chat_id=%s",
        (source_id,)
    )
    rows = cursor.fetchall()

    for (dest_string,) in rows:
        dest_ids = dest_string.split(",")

        for dest_id in dest_ids:
            try:
                await message.copy_to(int(dest_id))
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