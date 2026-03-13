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


# ════════════════════════════════════════════════
#   UI TEXT TEMPLATES
# ════════════════════════════════════════════════

WELCOME_NEW = (
    "📡 *ForwardBot*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Hey {name}! 👋 Welcome aboard.\n\n"
    "I can automatically forward messages\n"
    "from any channel to multiple destinations —\n"
    "with filters, blacklists & smart sync.\n\n"
    "✨ _Let's set up your first rule._"
)

WELCOME_BACK = (
    "📡 *ForwardBot*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Welcome back, {name}! 👋\n\n"
    "What would you like to do today?"
)

HELP_TEXT = (
    "❓ *How ForwardBot works*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "1️⃣  Create a rule — pick a *source* channel\n"
    "2️⃣  Add one or more *destination* channels\n"
    "3️⃣  I'll forward every new message automatically\n\n"
    "🎛 *Filters* — only forward certain message types\n"
    "🚫 *Blacklist* — block messages with certain keywords\n"
    "⏸ *Pause* — stop a rule without deleting it\n"
    "✏️ *Edit* — change destinations anytime\n\n"
    "⚠️ _I must be an admin in both the source\n"
    "and destination channels to work._"
)

NO_RULES_TEXT = (
    "📭 *No rules yet*\n\n"
    "You haven't set up any forwarding rules.\n"
    "Tap the button below to create your first one!"
)

STEP1_TEXT = (
    "📥 *Step 1 of 2 — Source Channel*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Forward any post from the channel\n"
    "you want to *copy messages FROM*.\n\n"
    "⚠️ _Make sure I'm an admin there first._"
)

STEP2_TEXT = (
    "📤 *Step 2 of 2 — Destination Channels*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Forward a post from each channel\n"
    "you want to *send messages TO*.\n\n"
    "You can add multiple destinations.\n"
    "Send /done when you're finished."
)

FILTER_TEXT = (
    "🎛 *Message Filters*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Choose which message types to forward.\n"
    "Tap to toggle on / off."
)


# ════════════════════════════════════════════════
#   KEYBOARDS
# ════════════════════════════════════════════════

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ New Forwarding Rule", callback_data="set_rules")],
        [InlineKeyboardButton(text="📋 My Rules",            callback_data="my_rules")],
        [InlineKeyboardButton(text="❓ How it works",        callback_data="help")],
    ])


def no_rules_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Create First Rule", callback_data="set_rules")],
        [InlineKeyboardButton(text="🏠 Home",              callback_data="home")],
    ])


def setup_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Set Source Channel",       callback_data="add_source")],
        [InlineKeyboardButton(text="📤 Add Destination Channel",  callback_data="add_destination")],
        [InlineKeyboardButton(text="🏠 Back to Home",             callback_data="home")],
    ])


def rule_action_keyboard(rid, is_active):
    toggle_label = "⏸ Pause" if is_active else "▶️ Resume"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Edit",     callback_data=f"edit_{rid}"),
            InlineKeyboardButton(text=toggle_label,  callback_data=f"toggle_{rid}"),
            InlineKeyboardButton(text="🗑 Delete",   callback_data=f"del_{rid}"),
        ]
    ])


def edit_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Destination",     callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove Destination",  callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Message Filters",    callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist Words",    callback_data="edit_blacklist")],
        [
            InlineKeyboardButton(text="💾 Save & Exit", callback_data="edit_done"),
            InlineKeyboardButton(text="✖️ Cancel",       callback_data="edit_cancel"),
        ],
    ])


def filter_keyboard(filters: dict):
    def btn(name, icon):
        on = filters.get(name)
        return InlineKeyboardButton(
            text=f"✅ {icon} {name.capitalize()}" if on else f"☐ {icon} {name.capitalize()}",
            callback_data=f"filter_{name}"
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("all", "♾️")],
        [btn("text", "💬"), btn("photo", "🖼"), btn("video", "🎬")],
        [btn("audio", "🎵"), btn("document", "📄"), btn("link", "🔗")],
        [
            InlineKeyboardButton(text="⬅️ Back",  callback_data="filter_back"),
            InlineKeyboardButton(text="💾 Save",  callback_data="filter_save"),
        ]
    ])


def blacklist_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Keywords",    callback_data="bl_add")],
        [InlineKeyboardButton(text="➖ Remove Keywords", callback_data="bl_remove")],
        [InlineKeyboardButton(text="⬅️ Back",            callback_data="bl_back")],
    ])


def help_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Create a Rule", callback_data="set_rules")],
        [InlineKeyboardButton(text="🏠 Home",          callback_data="home")],
    ])


# ════════════════════════════════════════════════
#   UI TEXT BUILDERS
# ════════════════════════════════════════════════

def rule_card_text(src_name, dst_names, is_active, rule_index):
    status = "🟢 Active" if is_active else "⏸ Paused"
    dests = "\n".join(f"   └─ 📤 {d}" for d in dst_names)
    return (
        f"*Rule #{rule_index}*  •  {status}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📥 *From:* {src_name}\n"
        f"{dests}"
    )


def edit_menu_text(src_name):
    return (
        f"✏️ *Editing Rule*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📥 Source: *{src_name}*\n\n"
        f"What would you like to change?"
    )


def blacklist_text(keywords):
    kw_display = (
        "\n".join(f"  • `{k.strip()}`" for k in keywords.split(",") if k.strip())
        if keywords and keywords.strip()
        else "  _No keywords yet_"
    )
    return (
        "🚫 *Blacklist Keywords*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Messages containing these words\n"
        "will *not* be forwarded:\n\n"
        f"{kw_display}"
    )


# ════════════════════════════════════════════════
#   DATABASE HELPERS
# ════════════════════════════════════════════════

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
            InlineKeyboardButton(text=f"➖ {name}", callback_data=f"remove_{d}")
        ])
    kb.append([
        InlineKeyboardButton(text="✅ Done", callback_data="edit_done")
    ])
    await call.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


def toggle_rule(rule_id, user_id):
    cursor.execute(
        "UPDATE rules SET is_active = NOT is_active WHERE id=%s AND user_id=%s",
        (rule_id, user_id)
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
        "SELECT id, source_chat_id, destination_chat_ids, is_active FROM rules WHERE user_id=%s",
        (user_id,)
    )
    return cursor.fetchall()


def delete_rule(rule_id, user_id):
    cursor.execute(
        "DELETE FROM rules WHERE id=%s AND user_id=%s",
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


# ════════════════════════════════════════════════
#   COMMAND HANDLERS
# ════════════════════════════════════════════════

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    uid, name, username = user.id, user.first_name, user.username

    existing = get_user(uid)
    if existing:
        text = WELCOME_BACK.format(name=name)
    else:
        save_user(uid, name, username)
        text = WELCOME_NEW.format(name=name)

    await message.answer(text, reply_markup=main_menu(), parse_mode="Markdown")


# ════════════════════════════════════════════════
#   HOME / HELP
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "home")
async def go_home(call: types.CallbackQuery):
    name = call.from_user.first_name
    await call.message.answer(
        WELCOME_BACK.format(name=name),
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(lambda c: c.data == "help")
async def help_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        HELP_TEXT,
        reply_markup=help_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()


# ════════════════════════════════════════════════
#   MY RULES
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "my_rules")
async def show_rules(call: types.CallbackQuery):
    rules = get_user_rules(call.from_user.id)

    if not rules:
        await call.message.answer(
            NO_RULES_TEXT,
            reply_markup=no_rules_keyboard(),
            parse_mode="Markdown"
        )
        await call.answer()
        return

    await call.message.answer(
        "📋 *Your Forwarding Rules*\n━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

    for i, (rid, src_id, dst_string, is_active) in enumerate(rules, 1):
        src_name = await get_chat_name(int(src_id))
        dst_names = [await get_chat_name(int(d)) for d in dst_string.split(",")]

        await call.message.answer(
            rule_card_text(src_name, dst_names, is_active, i),
            reply_markup=rule_action_keyboard(rid, is_active),
            parse_mode="Markdown"
        )

    await call.answer()


@dp.callback_query(lambda c: c.data == "noop")
async def noop_handler(call: types.CallbackQuery):
    await call.answer()


# ════════════════════════════════════════════════
#   DELETE / TOGGLE
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_rule_btn(call: types.CallbackQuery):
    rule_id = int(call.data.split("_")[1])
    delete_rule(rule_id, call.from_user.id)
    await call.message.answer(
        "🗑 *Rule deleted.*",
        parse_mode="Markdown"
    )
    await show_rules(call)
    await call.answer()


@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_rule_btn(call: types.CallbackQuery):
    rule_id = int(call.data.split("_")[1])
    toggle_rule(rule_id, call.from_user.id)
    await call.answer("✅ Rule status updated", show_alert=False)
    await show_rules(call)


# ════════════════════════════════════════════════
#   EDIT RULE
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data.startswith("edit_") and c.data[5:].isdigit())
async def edit_rule(call: types.CallbackQuery, state: FSMContext):
    rule_id = int(call.data.split("_")[1])

    cursor.execute(
        "SELECT source_chat_id, destination_chat_ids, filter_types, blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()

    if not row:
        await call.answer("Rule not found", show_alert=True)
        return

    src_id, dst_ids, filter_types, _ = row

    saved_filters = filter_types.split(",") if filter_types else ["all"]
    filter_dict = {
        "all":      1 if "all"      in saved_filters else 0,
        "text":     1 if "text"     in saved_filters else 0,
        "photo":    1 if "photo"    in saved_filters else 0,
        "video":    1 if "video"    in saved_filters else 0,
        "audio":    1 if "audio"    in saved_filters else 0,
        "document": 1 if "document" in saved_filters else 0,
        "link":     1 if "link"     in saved_filters else 0,
    }

    await state.update_data(
        rule_id=rule_id,
        destinations=dst_ids.split(","),
        filters=filter_dict
    )

    src_name = await get_chat_name(int(src_id))

    await call.message.edit_text(
        edit_menu_text(src_name),
        reply_markup=edit_menu_keyboard(),
        parse_mode="Markdown"
    )

    await state.set_state(EditRuleState.ChoosingAction)
    await call.answer()


@dp.callback_query(lambda c: c.data == "edit_cancel")
async def edit_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await show_rules(call)
    await call.answer()


@dp.callback_query(lambda c: c.data == "edit_add")
async def edit_add(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.AddingDestination)

    await call.message.edit_text(
        "📤 *Add Destination Channel*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Forward a post from each channel\n"
        "you want to add as a destination.\n\n"
        "You can add multiple. Press 💾 *Save & Exit* when done.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💾 Save & Exit", callback_data="edit_done")],
            [InlineKeyboardButton(text="✖️ Cancel",       callback_data="edit_cancel")],
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(EditRuleState.ChoosingAction, lambda c: c.data == "edit_remove")
async def edit_remove(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.RemovingDestination)
    await call.message.edit_text(
        "➖ *Remove Destination*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Tap a channel to remove it:"
    , parse_mode="Markdown")
    await send_remove_ui(call, state)
    await call.answer()


@dp.callback_query(EditRuleState.RemovingDestination, lambda c: c.data.startswith("remove_"))
async def remove_destination(call: types.CallbackQuery, state: FSMContext):
    remove_id = call.data.split("_")[1]
    data = await state.get_data()
    destinations = data.get("destinations", [])

    if remove_id in destinations:
        destinations.remove(remove_id)
        await state.update_data(destinations=destinations)

    await send_remove_ui(call, state)
    await call.answer("❌ Removed")


@dp.callback_query(lambda c: c.data == "edit_done")
async def edit_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]
    destinations = data["destinations"]

    if not destinations:
        await call.answer("❌ A rule must have at least one destination.", show_alert=True)
        return

    filters = data.get("filters", {"all": 1})
    enabled = [k for k, v in filters.items() if v == 1]
    filter_string = ",".join(enabled)
    dest_string = ",".join(destinations)

    cursor.execute(
        "UPDATE rules SET destination_chat_ids=%s, filter_types=%s WHERE id=%s AND user_id=%s",
        (dest_string, filter_string, rule_id, call.from_user.id)
    )
    db.commit()

    await state.clear()
    await call.message.delete()
    await call.answer("✅ Rule updated!", show_alert=False)
    await show_rules(call)


# ════════════════════════════════════════════════
#   FILTERS
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "edit_filters")
async def edit_filters(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters = data.get("filters", {
        "all": 1, "text": 0, "photo": 0, "video": 0,
        "audio": 0, "document": 0, "link": 0
    })
    await state.update_data(filters=filters)
    await call.message.edit_text(
        FILTER_TEXT,
        reply_markup=filter_keyboard(filters),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(
    lambda c: c.data.startswith("filter_")
    and c.data not in ("filter_back", "filter_save")
)
async def toggle_filter(call: types.CallbackQuery, state: FSMContext):
    key = call.data.replace("filter_", "")
    data = await state.get_data()
    filters = data.get("filters", {
        "all": 1, "text": 0, "photo": 0, "video": 0,
        "audio": 0, "document": 0, "link": 0
    })

    if key == "all":
        filters = {k: 0 for k in filters}
        filters["all"] = 1
    else:
        filters["all"] = 0
        filters[key] = 1 if not filters.get(key, 0) else 0
        if not any(filters.values()):
            filters["all"] = 1

    await state.update_data(filters=filters)
    await call.message.edit_reply_markup(reply_markup=filter_keyboard(filters))
    await call.answer()


@dp.callback_query(lambda c: c.data == "filter_back")
async def filter_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data.get("rule_id")

    cursor.execute(
        "SELECT source_chat_id FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()
    src_name = await get_chat_name(int(row[0])) if row else "Unknown"

    await call.message.edit_text(
        edit_menu_text(src_name),
        reply_markup=edit_menu_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()


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

    await state.set_state(EditRuleState.ChoosingAction)

    cursor.execute(
        "SELECT source_chat_id FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()
    src_name = await get_chat_name(int(row[0])) if row else "Unknown"

    await call.message.edit_text(
        "✅ *Filters saved!*\n\n" + edit_menu_text(src_name),
        reply_markup=edit_menu_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer("✅ Filters saved")


# ════════════════════════════════════════════════
#   BLACKLIST
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "edit_blacklist")
async def edit_blacklist(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]

    cursor.execute(
        "SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()
    current = row[0] if row and row[0] else ""

    await call.message.edit_text(
        blacklist_text(current),
        reply_markup=blacklist_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(lambda c: c.data == "bl_add")
async def blacklist_add_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.AddingBlacklist)
    await call.message.edit_text(
        "➕ *Add Blacklist Keywords*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Send keywords separated by commas.\n\n"
        "Example: `spam, scam, crypto, prize`",
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(EditRuleState.AddingBlacklist)
async def add_blacklist_keywords(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rule_id = data["rule_id"]

    new_words = [w.strip().lower() for w in message.text.split(",") if w.strip()]

    cursor.execute(
        "SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, message.from_user.id)
    )
    row = cursor.fetchone()
    existing = row[0].split(",") if row and row[0] else []

    updated = list(set(existing + new_words))
    updated_string = ",".join(updated)

    cursor.execute(
        "UPDATE rules SET blacklist_keywords=%s WHERE id=%s AND user_id=%s",
        (updated_string, rule_id, message.from_user.id)
    )
    db.commit()

    await state.set_state(EditRuleState.ChoosingAction)
    await message.answer(
        f"✅ *{len(new_words)} keyword(s) added to blacklist.*",
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "bl_remove")
async def blacklist_remove_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.RemovingBlacklist)
    await call.message.edit_text(
        "➖ *Remove Blacklist Keywords*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Send the keywords you want to remove,\n"
        "separated by commas.\n\n"
        "Example: `crypto, prize`",
        parse_mode="Markdown"
    )
    await call.answer()


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
        await message.answer("⚠️ No blacklist keywords found.")
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
    await message.answer(
        "🗑 *Selected keywords removed from blacklist.*",
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "bl_back")
async def blacklist_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rule_id = data.get("rule_id")

    cursor.execute(
        "SELECT source_chat_id FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()
    src_name = await get_chat_name(int(row[0])) if row else "Unknown"

    await state.set_state(EditRuleState.ChoosingAction)
    await call.message.edit_text(
        edit_menu_text(src_name),
        reply_markup=edit_menu_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()


# ════════════════════════════════════════════════
#   SETUP FLOW (New Rule)
# ════════════════════════════════════════════════

@dp.callback_query()
async def button_handler(call: types.CallbackQuery, state: FSMContext):
    if call.data == "set_rules":
        await call.message.answer(
            "⚡ *New Forwarding Rule*\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "Let's set up your rule step by step:",
            reply_markup=setup_menu(),
            parse_mode="Markdown"
        )

    elif call.data == "add_source":
        await call.message.answer(STEP1_TEXT, parse_mode="Markdown")
        await state.set_state(RuleState.Waiting_source)

    elif call.data == "add_destination":
        await call.message.answer(STEP2_TEXT, parse_mode="Markdown")
        await state.set_state(RuleState.Waiting_destination)

    await call.answer()


@dp.message(EditRuleState.AddingDestination)
async def add_destination(message: types.Message, state: FSMContext):
    if not message.forward_from_chat:
        await message.answer("⚠️ Please forward a post from a channel.")
        return

    channel_id = message.forward_from_chat.id
    data = await state.get_data()
    destinations = data["destinations"]

    if str(channel_id) in destinations:
        await message.answer("⚠️ This channel is already added.")
        return

    destinations.append(str(channel_id))
    await state.update_data(destinations=destinations)

    name = await get_chat_name(channel_id)
    await message.answer(
        f"✅ *{name}* added as destination!\n\nForward another channel or press 💾 Save & Exit.",
        parse_mode="Markdown"
    )


@dp.message(RuleState.Waiting_source)
async def get_source(message: types.Message, state: FSMContext):
    if message.forward_from_chat is not None:
        channel = message.forward_from_chat.id
        try:
            chat = await bot.get_chat(channel)
            member = await bot.get_chat_member(chat.id, bot.id)

            if member.status not in ["administrator", "creator"]:
                await message.answer(
                    "⚠️ I'm not an admin in that channel yet.\n"
                    "Please make me an admin and try again."
                )
                return

            await state.update_data(source=chat.id)
            src_name = await get_chat_name(chat.id)
            await message.answer(
                f"✅ *Source set:* {src_name}\n\n"
                f"{STEP2_TEXT}",
                parse_mode="Markdown"
            )

        except:
            await message.answer("❌ Invalid channel or I can't access it.")
    else:
        await message.answer("⚠️ Please forward a post from a channel — not a regular message.")


@dp.message(RuleState.Waiting_destination)
async def get_destination(message: types.Message, state: FSMContext):
    if message.text == "/done":
        data = await state.get_data()
        source_id = data.get("source")
        destinations = data.get("destinations", [])

        if not source_id or not destinations:
            await message.answer(
                "❌ *Setup incomplete.*\n\n"
                "You need a source and at least one destination.",
                parse_mode="Markdown"
            )
            await state.clear()
            return

        dest_string = ",".join(map(str, destinations))
        save_rule(message.from_user.id, source_id, dest_string)

        await message.answer(
            "🎉 *Rule created!*\n\n"
            "Forwarding is now active.\n"
            "You can manage it from *My Rules*.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        await state.clear()
        return

    if message.forward_from_chat:
        channel = message.forward_from_chat.id
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)

        if member.status not in ["administrator", "creator"]:
            await message.answer(
                "⚠️ I'm not an admin in that channel yet.\n"
                "Make me an admin and try again."
            )
            return

        data = await state.get_data()
        destinations = data.get("destinations", [])

        if channel not in destinations:
            destinations.append(channel)
            await state.update_data(destinations=destinations)
            name = await get_chat_name(channel)
            await message.answer(
                f"✅ *{name}* added!\n\n"
                f"Forward another channel or send /done to finish.",
                parse_mode="Markdown"
            )
        else:
            await message.answer("⚠️ This channel is already added.")
    else:
        await message.answer("⚠️ Please forward a post from a channel.")


# ════════════════════════════════════════════════
#   FORWARDING ENGINE
# ════════════════════════════════════════════════

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


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def contains_blacklist(text: str, blacklist_string: str) -> bool:
    if not text or not blacklist_string:
        return False

    original   = text.lower()
    normalized = normalize_text(text)
    blacklist  = [w.strip().lower() for w in blacklist_string.split(",") if w.strip()]

    for word in blacklist:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, original):
            return True
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

    msg_type     = get_message_type(message)
    text_content = message.text or message.caption or ""

    for dest_string, filter_types, blacklist_keywords in rows:
        allowed = filter_types.split(",")

        if "all" not in allowed and msg_type not in allowed:
            continue

        if contains_blacklist(text_content, blacklist_keywords):
            print(f"Blocked message due to blacklist: {text_content[:50]}")
            continue

        for dest_id in dest_string.split(","):
            try:
                sent_msg = await message.copy_to(int(dest_id))
                cursor.execute(
                    """INSERT INTO message_map
                    (source_chat_id, source_message_id, destination_chat_id, destination_message_id)
                    VALUES (%s,%s,%s,%s)""",
                    (message.chat.id, message.message_id, int(dest_id), sent_msg.message_id)
                )
            except:
                pass


@dp.edited_channel_post()
async def handle_edit(message: types.Message):
    source_chat = message.chat.id
    source_msg  = message.message_id

    cursor.execute(
        """SELECT destination_chat_id, destination_message_id
           FROM message_map
           WHERE source_chat_id=%s AND source_message_id=%s""",
        (source_chat, source_msg)
    )
    rows = cursor.fetchall()

    if not rows:
        return

    new_text = message.text or message.caption

    for dest_chat, dest_msg in rows:
        try:
            if new_text:
                if message.text:
                    await bot.edit_message_text(
                        chat_id=dest_chat, message_id=dest_msg, text=new_text
                    )
                elif message.caption:
                    await bot.edit_message_caption(
                        chat_id=dest_chat, message_id=dest_msg, caption=new_text
                    )
            else:
                await bot.delete_message(chat_id=dest_chat, message_id=dest_msg)
        except:
            pass


# ════════════════════════════════════════════════
#   CATCH-ALL
# ════════════════════════════════════════════════

@dp.message()
async def any_message(message: types.Message):
    user = message.from_user
    uid  = user.id

    if not get_user(uid):
        save_user(uid, user.first_name, user.username)

    await message.answer(
        "👋 Use the menu to get started:",
        reply_markup=main_menu()
    )


# ════════════════════════════════════════════════
#   MAIN
# ════════════════════════════════════════════════

async def main():
    await dp.start_polling(bot)

asyncio.run(main())