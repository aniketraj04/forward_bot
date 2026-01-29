import asyncio
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import RuleState, EditRuleState
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

async def get_chat_name(chat_id: int) -> str:
    try:
        chat = await bot.get_chat(chat_id)
        return chat.title or chat.username or str(chat_id)
    except:
        return str(chat_id)
    
def toggle_rule(rule_id, user_id):
    cursor.execute(
        "UPDATE rules SET is_active = NOT is_active WHERE id=%s AND user_id=%s",(rule_id, user_id)

    )
    db.commit()

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
        "SELECT id, source_chat_id, destination_chat_ids, is_active  FROM rules WHERE user_id=%s",
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
        await call.message.answer(
            "😕 You haven’t created any forwarding rules yet.\n"
            "➕ Tap \"Set forwarding rules\" to start.",
            reply_markup=main_menu()
        )
        await call.answer()
        return
    kb = []

    for rid, src_id, dst_string, is_active in rules:
        # Source name
        src_name = await get_chat_name(int(src_id))

        # Destination names
        dst_ids = dst_string.split(",")
        dst_names = []
        for d in dst_ids:
            name = await get_chat_name(int(d))
            dst_names.append(name)

        pretty_text = f"{src_name} → {', '.join(dst_names)}"
        
        status_icon = "🟢 ON" if is_active else "⏸ OFF"
        toggle_text = "⏸ Pause" if is_active else "▶️ Resume"

        kb.append([
            InlineKeyboardButton(
                text=f"{pretty_text} ({status_icon})",
                callback_data="noop"
            )
        ])

        kb.append([
            InlineKeyboardButton(
                text = "✏️ Edit",
                callback_data=f"edit_{rid}"
            ),
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=f"toggle_{rid}"
            ),
            InlineKeyboardButton(
                text="🗑 Delete",
                callback_data=f"del_{rid}"
            )
        ])


    await call.message.answer(
        "📋 Your forwarding rules:",
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


@dp.callback_query(lambda c: c.data.startswith("edit_") and c.data[5:].isdigit())
async def edit_rule(call: types.CallbackQuery, state: FSMContext):

    rule_id = int(call.data.split("_")[1])

    #fetch rule
    cursor.execute(
        "SELECT destination_chat_ids FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()

    if not row:
        await call.answer("Rule not found")
        return
    
    destinations = row[0].split(",")

    await state.update_data(
        rule_id=rule_id,
        destinations=destinations
    )

    kb = [
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="✅ Done", callback_data="edit_done")]
    ]


    await call.message.answer(
        "✏️ Edit rule:\nChoose what you want to do",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

    await state.set_state(EditRuleState.ChoosingAction)
    await call.answer()

@dp.callback_query(lambda c: c.data=="edit_add")
async def edit_add(call: types.CallbackQuery,  state: FSMContext):
    await call.message.answer("Forward a post from the channel to ADD")
    await state.set_state(EditRuleState.AddingDestination)
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_rule_btn(call: types.CallbackQuery):
    rule_id = int(call.data.split("_")[1])

    toggle_rule(rule_id, call.from_user.id)

    await call.answer("Rule status updated")
    await show_rules(call)

# start change from here time:- 8:12pm 29
@dp.callback_query(EditRuleState.ChoosingAction, lambda c: c.data == "edit_remove")
async def edit_remove(call: types.CallbackQuery, state: FSMContext):

    data = await state.get_data()
    destinations = data["destinations"]

    kb = []
    for d in destinations:
        name = await get_chat_name(int(d))
        kb.append([
            InlineKeyboardButton(
                text=f"➖ {name}",
                callback_data=f"remove_{d}"
            )
        ])

    await call.message.answer(
        "Select destination to remove:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

    await state.set_state(EditRuleState.RemovingDestination)
    await call.answer()


@dp.callback_query(EditRuleState.RemovingDestination, lambda c: c.data.startswith("remove_"))
async def remove_destination(call: types.CallbackQuery, state: FSMContext):

    remove_id = call.data.split("_")[1]

    data = await state.get_data()
    destinations = data["destinations"]

    destinations.remove(remove_id)
    await state.update_data(destinations=destinations)

    await call.answer("❌ Removed")

@dp.callback_query(lambda c: c.data == "edit_done")
async def edit_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]
    destinations = data["destinations"]

    if not destinations:
        await call.answer(
            "❌ A rule must have at least one destination",
            show_alert=True
        )
        return

    dest_string = ",".join(destinations)


    cursor.execute(
        "UPDATE rules SET destination_chat_ids=%s WHERE id=%s AND user_id=%s",
        (dest_string, rule_id, call.from_user.id)
    )
    db.commit()

    await state.clear()
    await call.message.answer("✅ Rule updated successfully")
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

####
@dp.message(EditRuleState.AddingDestination)
async def add_destination(message: types.Message, state: FSMContext):
    if not message.forward_from_chat:
        await message.answer("Please forward a channel post")
        return

    channel_id = message.forward_from_chat.id
    data = await state.get_data()
    destinations = data["destinations"]

    if str(channel_id) in destinations:
        await message.answer("Already exists")
        return

    destinations.append(str(channel_id))
    await state.update_data(destinations=destinations)

    await message.answer("✅ Destination added")


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
        "SELECT destination_chat_ids FROM rules WHERE source_chat_id=%s AND is_active=1",
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