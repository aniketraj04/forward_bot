import os
import asyncio
import mysql.connector
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
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
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT", 3306)),
    autocommit=True 
)

# HELPER: This prevents "MySQL Connection Lost" errors on Railway
def get_cursor():
    try:
        db.ping(reconnect=True, attempts=3, delay=1)
    except:
        pass
    return db.cursor()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE FUNCTIONS UPDATED WITH get_cursor() ---

def toggle_rule(rule_id, user_id):
    cursor = get_cursor()
    cursor.execute(
        "UPDATE rules SET is_active = NOT is_active WHERE id=%s AND user_id=%s",(rule_id, user_id)
    )

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

def delete_rule(rule_id, user_id):
    cursor = get_cursor()
    cursor.execute(
        "DELETE FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, user_id)
    )

def save_rule(user_id, source_id, destination_ids_str):
    try:
        cursor = get_cursor()
        cursor.execute(
            "INSERT INTO rules (user_id, source_chat_id, destination_chat_ids) VALUES (%s,%s,%s)",
            (user_id, source_id, destination_ids_str)
        )
        return True
    except mysql.connector.errors.IntegrityError:
        return False

# --- UI & HANDLERS ---

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
        kb.append([InlineKeyboardButton(text=f"➖ {name}", callback_data=f"remove_{d}")])
    kb.append([InlineKeyboardButton(text="✅ Done", callback_data="edit_done")])
    await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="set forwarding rules", callback_data="set_rules")],
        [InlineKeyboardButton(text="my rules", callback_data="my_rules")]
    ])

def rules_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" ADD SOURCE", callback_data="add_source")],
        [InlineKeyboardButton(text=" ADD DESTINATION", callback_data="add_destination")]
    ])

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    uid, name, username = user.id, user.first_name, user.username
    existing = get_user(uid)
    if existing:
        text = f"Welcome back, {name}! 😄"
    else:
        save_user(uid, name, username)
        text = f"Hello {name}! I've saved your info."
    await message.answer(text + "\n\nChoose an option:", reply_markup=main_menu())

@dp.callback_query(lambda c: c.data == "my_rules")
async def show_rules(call: types.CallbackQuery):
    rules = get_user_rules(call.from_user.id)
    if not rules:
        await call.message.answer("No rules yet.", reply_markup=main_menu())
        await call.answer()
        return
    kb = []
    for rid, src_id, dst_string, is_active in rules:
        src_name = await get_chat_name(int(src_id))
        dst_names = [await get_chat_name(int(d)) for d in dst_string.split(",")]
        pretty_text = f"{src_name} → {', '.join(dst_names)}"
        status_icon = "🟢 ON" if is_active else "⏸ OFF"
        toggle_text = "⏸ Pause" if is_active else "▶️ Resume"
        kb.append([InlineKeyboardButton(text=f"{pretty_text} ({status_icon})", callback_data="noop")])
        kb.append([
            InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit_{rid}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_{rid}"),
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{rid}")
        ])
    await call.message.answer("📋 Your rules:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

@dp.callback_query(lambda c: c.data == "edit_filters")
async def edit_filters(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters = data.get("filters", {"all": 1, "text": 0, "photo": 0, "video": 0, "audio": 0, "document": 0, "link": 0})
    await state.update_data(filters=filters)
    await call.message.edit_text("🎛 Select allowed message types:", reply_markup=filter_keyboard(filters))
    await call.answer()

@dp.callback_query(lambda c: c.data == "filter_save")
async def filter_save(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id, filters = data["rule_id"], data.get("filters", {"all": 1})
    enabled = [k for k, v in filters.items() if v == 1]
    filter_string = ",".join(enabled)
    cursor = get_cursor()
    cursor.execute("UPDATE rules SET filter_types=%s WHERE id=%s AND user_id=%s", (filter_string, rule_id, call.from_user.id))
    await state.set_state(EditRuleState.ChoosingAction)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="✅ Done", callback_data="edit_done"), InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")]
    ])
    await call.message.edit_text("✅ Filters saved.\n\n✏️ Edit rule:", reply_markup=kb)
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("edit_") and c.data[5:].isdigit())
async def edit_rule(call: types.CallbackQuery, state: FSMContext):
    rule_id = int(call.data.split("_")[1])
    cursor = get_cursor()
    cursor.execute("SELECT destination_chat_ids, filter_types FROM rules WHERE id=%s AND user_id=%s", (rule_id, call.from_user.id))
    row = cursor.fetchone()
    if not row:
        await call.answer("Rule not found")
        return
    saved_filters = row[1].split(",") if row[1] else ["all"]
    filter_dict = {k: (1 if k in saved_filters else 0) for k in ["all", "text", "photo", "video", "audio", "document", "link"]}
    await state.update_data(rule_id=rule_id, destinations=row[0].split(","), filters=filter_dict)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add destination", callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Filters", callback_data="edit_filters")],
        [InlineKeyboardButton(text="✅ Done", callback_data="edit_done"), InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")]
    ])
    await call.message.edit_text("✏️ Edit rule:", reply_markup=kb)
    await state.set_state(EditRuleState.ChoosingAction)
    await call.answer()

@dp.callback_query(lambda c: c.data == "edit_done")
async def edit_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id, destinations = data["rule_id"], data["destinations"]
    if not destinations:
        await call.answer("❌ Need at least one destination", show_alert=True)
        return
    filters = data.get("filters", {"all": 1})
    filter_string = ",".join([k for k, v in filters.items() if v == 1])
    dest_string = ",".join(destinations)
    cursor = get_cursor()
    cursor.execute("UPDATE rules SET destination_chat_ids=%s, filter_types=%s WHERE id=%s AND user_id=%s", (dest_string, filter_string, rule_id, call.from_user.id))
    await state.clear()
    await call.message.delete()
    await show_rules(call)
    await call.answer("✅ Updated")

@dp.channel_post()
async def forward_from_source(message: types.Message):
    source_id = message.chat.id
    cursor = get_cursor()
    cursor.execute("SELECT destination_chat_ids, filter_types FROM rules WHERE source_chat_id=%s AND is_active=1", (source_id,))
    rows = cursor.fetchall()
    msg_type = get_message_type(message)
    for dest_string, filter_types in rows:
        allowed = filter_types.split(",")
        if "all" not in allowed and msg_type not in allowed:
            continue
        for dest_id in dest_string.split(","):
            try:
                await message.copy_to(int(dest_id))
            except:
                pass

# --- REMAINING BOILERPLATE ---
# (Keep your toggle_filter, any_message, and get_message_type functions here)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())