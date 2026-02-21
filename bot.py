import asyncio 
import os
import re
from dotenv import load_dotenv
load_dotenv()
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import RuleState, EditRuleState
from aiogram.fsm.context import FSMContext



BOT_TOKEN = os.getenv("BOT_TOKEN")

db = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQL_DATABASE"), 
    port=int(os.getenv("MYSQLPORT", 3306)),
    autocommit=True 
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
    
async def send_remove_ui(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    destinations = data.get("destinations", [])

    kb = []

    for d in destinations:
        name = await get_chat_name(int(d))
        kb.append([
            InlineKeyboardButton(
                text=f"➖ {name}",
                callback_data=f"remove_{d}"
            )
        ])

    # DONE button (same screen)
    kb.append([
        InlineKeyboardButton(
            text="✅ Done",
            callback_data="edit_done"
        )
    ])

    await call.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

    
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

    # Fetch both destinations AND filters
    cursor.execute(
        "SELECT destination_chat_ids, filter_types, blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()

    if not row:
        await call.answer("Rule not found")
        return

    # Convert the saved comma-string back into a dictionary for the UI
    saved_filters = row[1].split(",") if row[1] else ["all"]
    filter_dict = {
        "all": 1 if "all" in saved_filters else 0,
        "text": 1 if "text" in saved_filters else 0,
        "photo": 1 if "photo" in saved_filters else 0,
        "video": 1 if "video" in saved_filters else 0,
        "audio": 1 if "audio" in saved_filters else 0,
        "document": 1 if "document" in saved_filters else 0,
        "link": 1 if "link" in saved_filters else 0
    }

    await state.update_data(
        rule_id=rule_id,
        destinations=row[0].split(","),
        filters=filter_dict
    )
    


    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist", callback_data="edit_blacklist")],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")
        ]
    ])

    await call.message.edit_text(
        "✏️ Edit rule:\nChoose what you want to do",
        reply_markup=kb
    )

    await state.set_state(EditRuleState.ChoosingAction)
    await call.answer()


@dp.callback_query(lambda c: c.data == "edit_cancel")
async def edit_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()

    await call.message.edit_text("📋 Your forwarding rules:")
    await show_rules(call)

    await call.answer()

@dp.callback_query(lambda c: c.data == "edit_add")
async def edit_add(call: types.CallbackQuery, state: FSMContext):

    await state.set_state(EditRuleState.AddingDestination)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")
        ]
    ])

    await call.message.edit_text(
        "📥 Forward a post from the channel to ADD destination\n\n"
        "You can add multiple channels.\n"
        "Press ✅ Done when finished or ❌ Cancel.",
        reply_markup=kb
    )

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

    await state.set_state(EditRuleState.RemovingDestination)

    await call.message.edit_text("Select destination to remove:")

    #  Render live removable list + Done button
    await send_remove_ui(call, state)

    await call.answer()


# function for filter buttons ui 
def filter_keyboard(filters: dict):
    def btn(name):
        return InlineKeyboardButton(
            text=f"✅ {name}" if filters.get(name) else f"⬜ {name}",
            callback_data=f"filter_{name}"
        )

    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("all")],
        [btn("text"), btn("photo"), btn("video")],
        [btn("audio"), btn("document"), btn("link")],
        [
            InlineKeyboardButton(text="⬅ Back", callback_data="filter_back"),
            InlineKeyboardButton(text="💾 Save", callback_data="filter_save")
        ]
    ])



# handjob for opening filters
@dp.callback_query(lambda c: c.data == "edit_filters")
async def edit_filters(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    filters = data.get("filters",{
        "all": 1, "text": 0, "photo": 0, "video": 0,
        "audio": 0, "document": 0, "link": 0
    })

    await state.update_data(filters=filters)

    await call.message.edit_text(
        "🎛 Select allowed message types:",
        reply_markup=filter_keyboard(filters)
    )

    await call.answer()



#Back button handler 
@dp.callback_query(lambda c: c.data == "filter_back")
async def filter_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist", callback_data="edit_blacklist")],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")
        ]
    ])

    await call.message.edit_text(
        "✏️ Edit rule:\nChoose what you want to do",
        reply_markup=kb
    )

    await call.answer()

# filter save button ka function 

@dp.callback_query(lambda c: c.data == "filter_save")
async def filter_save(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    rule_id = data["rule_id"]
    filters = data.get("filters", {"all": 1})

    enabled = [k for k, v in filters.items() if v == 1]
    filter_string = ",".join(enabled)

    cursor.execute(
        "UPDATE rules SET filter_types=%s WHERE id=%s AND user_id=%s",
        (filter_string, rule_id, call.from_user.id)
    )
    db.commit()

    # Go back to edit menu
    await state.set_state(EditRuleState.ChoosingAction)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist", callback_data="edit_blacklist")],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")
        ]
    ])

    await call.message.edit_text(
        "✅ Filters saved.\n\n✏️ Edit rule:\nChoose what you want to do",
        reply_markup=kb
    )

    await call.answer("Filters saved")

# black liist menu ui 
def blacklist_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Keywords", callback_data="bl_add")],
        [InlineKeyboardButton(text="➖ Remove Keywords", callback_data="bl_remove")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="bl_back")]
    ])


# Blacklist Panel handler 
@dp.callback_query(lambda c: c.data == "edit_blacklist")
async def edit_blacklist(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]

    cursor.execute(
        "SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()

    current = row[0] if row and row[0] else "None"

    text = (
        "🚫 Blacklist Keywords lets you stop forwarding posts that contain specific words.\n\n"
        f"Current Blacklist:\n{current}"
    )

    await call.message.edit_text(text, reply_markup=blacklist_keyboard())
    await call.answer()

#Add Keywords Button Handler
@dp.callback_query(lambda c: c.data == "bl_add")
async def blacklist_add_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.AddingBlacklist)

    await call.message.edit_text(
        "Please send the keywords you want to blacklist, separated by commas.\n\n"
        "For example: spam, scam, crypto"
    )
    await call.answer()

#Handle User Input
@dp.message(EditRuleState.AddingBlacklist)
async def add_blacklist_keywords(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]

    new_words = [w.strip().lower() for w in message.text.split(",") if w.strip()]

    # Fetch existing blacklist
    cursor.execute(
        "SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, message.from_user.id)
    )
    row = cursor.fetchone()

    existing = row[0].split(",") if row and row[0] else []

    # Merge + remove duplicates
    updated = list(set(existing + new_words))
    updated_string = ",".join(updated)

    cursor.execute(
        "UPDATE rules SET blacklist_keywords=%s WHERE id=%s AND user_id=%s",
        (updated_string, rule_id, message.from_user.id)
    )
    db.commit()

    await state.set_state(EditRuleState.ChoosingAction)

    await message.answer(
        f"✅ {len(new_words)} keywords added to blacklist."
    )

# Remove Keywords Handler for black list 
@dp.callback_query(lambda c: c.data == "bl_remove")
async def blacklist_remove_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.RemovingBlacklist)

    await call.message.edit_text(
        "Send the keywords you want to REMOVE from blacklist.\n\n"
        "Example: spam, scam"
    )
    await call.answer()

#
@dp.message(EditRuleState.RemovingBlacklist)
async def remove_blacklist_keywords(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]

    remove_words = [w.strip().lower() for w in message.text.split(",") if w.strip()]

    cursor.execute(
        "SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, message.from_user.id)
    )
    row = cursor.fetchone()

    if not row or not row[0]:
        await message.answer("No blacklist keywords found.")
        return

    existing = row[0].split(",")
    updated = [w for w in existing if w not in remove_words]
    updated_string = ",".join(updated)

    cursor.execute(
        "UPDATE rules SET blacklist_keywords=%s WHERE id=%s AND user_id=%s",
        (updated_string, rule_id, message.from_user.id)
    )
    db.commit()

    await state.set_state(EditRuleState.ChoosingAction)

    await message.answer("🗑 Selected keywords removed from blacklist.")

#back button handler for black list 

@dp.callback_query(lambda c: c.data == "bl_back")
async def blacklist_back(call: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist", callback_data="edit_blacklist")],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")
        ]
    ])

    await state.set_state(EditRuleState.ChoosingAction)
    await call.message.edit_text(
        "✏️ Edit rule:\nChoose what you want to do",
        reply_markup=kb
    )
    await call.answer()

# handle filter toggle clicks

@dp.callback_query(
    lambda c: c.data.startswith("filter_") 
    and c.data not in ("filter_back", "filter_save")
)
async def toggle_filter(call: types.CallbackQuery, state: FSMContext):
    key = call.data.replace("filter_", "")
    data = await state.get_data()
    
    # Default filters if not set
    filters = data.get("filters", {
        "all": 1, "text": 0, "photo": 0, "video": 0,
        "audio": 0, "document": 0, "link": 0
    })

    if key == "all":
        # Turning 'all' ON turns everything else OFF
        filters = {k: 0 for k in filters}
        filters["all"] = 1
    else:
        # Turning any specific filter ON turns 'all' OFF
        filters["all"] = 0
        filters[key] = 1 if not filters.get(key, 0) else 0
        
        # If the user unchecks EVERYTHING, default back to "all"
        if not any(filters.values()):
            filters["all"] = 1

    await state.update_data(filters=filters)
    await call.message.edit_reply_markup(reply_markup=filter_keyboard(filters))
    await call.answer()




@dp.callback_query(EditRuleState.RemovingDestination, lambda c: c.data.startswith("remove_"))
async def remove_destination(call: types.CallbackQuery, state: FSMContext):
    remove_id = call.data.split("_")[1]

    data = await state.get_data()
    destinations = data.get("destinations", [])

    if remove_id in destinations:
        destinations.remove(remove_id)
        await state.update_data(destinations=destinations)

    #  REAL-TIME UI UPDATE
    await send_remove_ui(call, state)

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
    
    #...
    filters = data.get("filters", {"all": 1})
    enabled = [k for k, v in filters.items() if v == 1]
    filter_string = ",".join(enabled)
    #..
    dest_string = ",".join(destinations)


    cursor.execute(
        "UPDATE rules SET destination_chat_ids=%s, filter_types=%s WHERE id=%s AND user_id=%s",
        (dest_string, filter_string, rule_id, call.from_user.id)
    )
    db.commit()

    await state.clear()
    await call.message.delete()
    await show_rules(call)
    await call.answer("✅ Rule updated")



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


def get_message_type(msg: types.Message):
    if msg.text and "http" in msg.text:
        return "link"
    if msg.text:
        return "text"
    if msg.photo:
        return "photo"
    if msg.video:
        return "video"
    if msg.audio:
        return "audio"
    if msg.document:
        return "document"
    return None

# balcklist check function 
def normalize_text(text: str) -> str:
    text = text.lower()
    # remove symbols like *, ., @ etc
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # remove extra spaces (for f u c k bypass)
    text = re.sub(r'\s+', ' ', text)
    return text


def contains_blacklist(text: str, blacklist_string: str) -> bool:
    if not text or not blacklist_string:
        return False

    # Original text
    original = text.lower()
    # Normalized text (anti-bypass)
    normalized = normalize_text(text)

    blacklist = [w.strip().lower() for w in blacklist_string.split(",") if w.strip()]

    for word in blacklist:
        # 1️⃣ Strict word match (safe)
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, original):
            return True
        
        # 2️⃣ Anti-bypass match (f*ck, f u c k, f.u.c.k)
        if word in normalized.replace(" ", ""):
            return True

    return False

@dp.channel_post()
async def forward_from_source(message: types.Message):
    source_id = message.chat.id

    cursor.execute(
        "SELECT destination_chat_ids, filter_types, blacklist_keywords FROM rules WHERE source_chat_id=%s AND is_active=1",
        (source_id,)
    )
    rows = cursor.fetchall()

    #  detect message type ONCE
    msg_type = get_message_type(message)

    # detect message text/caption once
    text_content = message.text or message.caption or ""

    for dest_string, filter_types, blacklist_keywords in rows:
        allowed = filter_types.split(",")

        # 1️⃣ FILTER CHECK (your existing system)
        if "all" not in allowed and msg_type not in allowed:
            continue

        # 2️⃣ BLACKLIST CHECK (NEW SMART FEATURE)
        if contains_blacklist(text_content, blacklist_keywords):
            print(f"Blocked message due to blacklist: {text_content}")
            continue  # Skip forwarding completely

        # 3️⃣ FORWARD ONLY IF CLEAN
        for dest_id in dest_string.split(","):
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