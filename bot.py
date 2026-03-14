import asyncio
import os
import re
from dotenv import load_dotenv
load_dotenv()
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import RuleState, EditRuleState, DelayState
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
    "⏱ *Delay* — wait N seconds before forwarding\n"
    "⏸ *Pause* — stop a rule without deleting it\n"
    "✏️ *Edit* — change destinations anytime\n\n"
    "⚠️ _I must be an admin in both the source\n"
    "and destination channels to work._"
)

NO_RULES_TEXT = (
    "📭 *No rules yet*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "You haven't set up any forwarding rules yet.\n"
    "Tap below to create your first one!"
)

FILTER_TEXT = (
    "🎛 *Message Filters*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Choose which message types to forward.\n"
    "Tap to toggle on / off."
)

STEP1_TEXT = (
    "📥 *Step 1 — Source Channel*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Forward any post from the channel\n"
    "you want to *copy messages FROM*.\n\n"
    "⚠️ _Make sure I'm an admin there first._"
)

STEP2_TEXT = (
    "📤 *Step 2 — Destination Channels*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "Forward a post from each channel\n"
    "you want to *send messages TO*.\n\n"
    "You can add multiple destinations.\n"
    "Send /done when finished."
)


# ════════════════════════════════════════════════
#   UI BUILDERS
# ════════════════════════════════════════════════

def rules_list_text(rules_data):
    if not rules_data:
        return NO_RULES_TEXT
    lines = ["📋 *Your Forwarding Rules*\n━━━━━━━━━━━━━━━━━"]
    for i, (rid, src_name, dst_names, is_active, delay_seconds) in enumerate(rules_data, 1):
        status = "🟢" if is_active else "⏸"
        delay_str = f" · ⏱ {delay_seconds}s" if delay_seconds and delay_seconds > 0 else ""
        dests = ", ".join(dst_names)
        lines.append(f"\n{status} *Rule #{i}*{delay_str}\n📥 _{src_name}_\n📤 _{dests}_")
    return "\n".join(lines)


def rules_list_keyboard(rules_data):
    if not rules_data:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Create First Rule", callback_data="set_rules")],
            [InlineKeyboardButton(text="🏠 Home",              callback_data="home")],
        ])
    kb = []
    for i, (rid, src_name, dst_names, is_active, delay_seconds) in enumerate(rules_data, 1):
        toggle_label = "⏸ Pause" if is_active else "▶️ Resume"
        kb.append([
            InlineKeyboardButton(text=f"✏️ Edit {i}",    callback_data=f"edit_{rid}"),
            InlineKeyboardButton(text=toggle_label,   callback_data=f"toggle_{rid}"),
            InlineKeyboardButton(text=f"🗑 Delet {i}",     callback_data=f"del_{rid}"),
        ])
    kb.append([InlineKeyboardButton(text="⚡ New Rule", callback_data="set_rules")])
    kb.append([InlineKeyboardButton(text="🏠 Home",     callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ New Forwarding Rule", callback_data="set_rules")],
        [InlineKeyboardButton(text="📋 My Rules",            callback_data="my_rules")],
        [InlineKeyboardButton(text="❓ How it works",        callback_data="help")],
    ])


def edit_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Destination",    callback_data="edit_add")],
        [InlineKeyboardButton(text="➖ Remove Destination", callback_data="edit_remove")],
        [InlineKeyboardButton(text="🎛 Message Filters",   callback_data="edit_filters")],
        [InlineKeyboardButton(text="🚫 Blacklist Words",   callback_data="edit_blacklist")],
        [InlineKeyboardButton(text="⏱ Set Delay",         callback_data="edit_delay")],
        [
            InlineKeyboardButton(text="💾 Save & Back", callback_data="edit_done"),
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
            InlineKeyboardButton(text="⬅️ Back", callback_data="filter_back"),
            InlineKeyboardButton(text="💾 Save", callback_data="filter_save"),
        ]
    ])


def blacklist_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Keywords",    callback_data="bl_add")],
        [InlineKeyboardButton(text="➖ Remove Keywords", callback_data="bl_remove")],
        [InlineKeyboardButton(text="⬅️ Back",            callback_data="bl_back")],
    ])


def edit_menu_text(src_name):
    return (
        "✏️ *Editing Rule*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"📥 Source: *{src_name}*\n\n"
        "What would you like to change?"
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
#   SHARED HELPERS
# ════════════════════════════════════════════════

async def get_chat_name(chat_id: int) -> str:
    try:
        chat = await bot.get_chat(chat_id)
        return chat.title or chat.username or str(chat_id)
    except:
        return str(chat_id)


async def fetch_rules_display(user_id):
    cursor.execute(
        "SELECT id, source_chat_id, destination_chat_ids, is_active, delay_seconds FROM rules WHERE user_id=%s",
        (user_id,)
    )
    rows = cursor.fetchall()
    result = []
    for rid, src_id, dst_string, is_active, delay_seconds in rows:
        src_name  = await get_chat_name(int(src_id))
        dst_names = [await get_chat_name(int(d)) for d in dst_string.split(",")]
        result.append((rid, src_name, dst_names, is_active, delay_seconds or 0))
    return result


async def edit_to_rules(call: types.CallbackQuery):
    rules_data = await fetch_rules_display(call.from_user.id)
    await call.message.edit_text(
        rules_list_text(rules_data),
        reply_markup=rules_list_keyboard(rules_data),
        parse_mode="Markdown"
    )


async def edit_to_home(call: types.CallbackQuery):
    await call.message.edit_text(
        WELCOME_BACK.format(name=call.from_user.first_name),
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


async def edit_to_edit_menu(call_or_message, user_id, rule_id, state):
    cursor.execute("SELECT source_chat_id FROM rules WHERE id=%s AND user_id=%s", (rule_id, user_id))
    row = cursor.fetchone()
    src_name = await get_chat_name(int(row[0])) if row else "Unknown"
    await state.set_state(EditRuleState.ChoosingAction)
    if isinstance(call_or_message, types.CallbackQuery):
        await call_or_message.message.edit_text(edit_menu_text(src_name), reply_markup=edit_menu_keyboard(), parse_mode="Markdown")
    else:
        await call_or_message.answer(edit_menu_text(src_name), reply_markup=edit_menu_keyboard(), parse_mode="Markdown")


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()


def save_user(user_id, first_name, username):
    cursor.execute("INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s)", (user_id, first_name, username))
    db.commit()


def toggle_rule(rule_id, user_id):
    cursor.execute("UPDATE rules SET is_active = NOT is_active WHERE id=%s AND user_id=%s", (rule_id, user_id))
    db.commit()


def delete_rule(rule_id, user_id):
    cursor.execute("DELETE FROM rules WHERE id=%s AND user_id=%s", (rule_id, user_id))
    db.commit()


def save_rule(user_id, source_id, destination_ids_str):
    try:
        cursor.execute("INSERT INTO rules (user_id, source_chat_id, destination_chat_ids) VALUES (%s,%s,%s)", (user_id, source_id, destination_ids_str))
        db.commit()
        return True
    except mysql.connector.errors.IntegrityError:
        return False


# ════════════════════════════════════════════════
#   /start  ← only place a NEW message is sent
# ════════════════════════════════════════════════

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    existing = get_user(user.id)
    if existing:
        text = WELCOME_BACK.format(name=user.first_name)
    else:
        save_user(user.id, user.first_name, user.username)
        text = WELCOME_NEW.format(name=user.first_name)
    await message.answer(text, reply_markup=main_menu(), parse_mode="Markdown")


# ════════════════════════════════════════════════
#   HOME / HELP
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "home")
async def go_home(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_to_home(call)
    await call.answer()


@dp.callback_query(lambda c: c.data == "help")
async def help_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Create a Rule", callback_data="set_rules")],
            [InlineKeyboardButton(text="⬅️ Back",          callback_data="home")],
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


# ════════════════════════════════════════════════
#   MY RULES
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "my_rules")
async def show_rules(call: types.CallbackQuery):
    await edit_to_rules(call)
    await call.answer()


# ════════════════════════════════════════════════
#   DELETE / TOGGLE
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_rule_btn(call: types.CallbackQuery):
    delete_rule(int(call.data.split("_")[1]), call.from_user.id)
    await edit_to_rules(call)
    await call.answer("🗑 Rule deleted")


@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_rule_btn(call: types.CallbackQuery):
    toggle_rule(int(call.data.split("_")[1]), call.from_user.id)
    await edit_to_rules(call)
    await call.answer("✅ Status updated")


# ════════════════════════════════════════════════
#   NEW RULE SETUP
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "set_rules")
async def set_rules_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        "⚡ *New Forwarding Rule*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Let's set it up step by step.\n\n"
        "Start by setting your *source channel*:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Set Source Channel",      callback_data="add_source")],
            [InlineKeyboardButton(text="📤 Add Destination Channel", callback_data="add_destination")],
            [InlineKeyboardButton(text="⬅️ Back",                    callback_data="my_rules")],
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.callback_query(lambda c: c.data == "add_source")
async def add_source_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        STEP1_TEXT,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="set_rules")]
        ]),
        parse_mode="Markdown"
    )
    await state.set_state(RuleState.Waiting_source)
    await call.answer()


@dp.callback_query(lambda c: c.data == "add_destination")
async def add_destination_btn_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        STEP2_TEXT,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Done — Save Rule", callback_data="save_new_rule")],
            [InlineKeyboardButton(text="⬅️ Back",             callback_data="set_rules")],
        ]),
        parse_mode="Markdown"
    )
    await state.set_state(RuleState.Waiting_destination)
    await call.answer()


@dp.message(RuleState.Waiting_source)
async def get_source(message: types.Message, state: FSMContext):
    if not message.forward_from_chat:
        await message.answer("⚠️ Please forward a post from a channel — not a regular message.")
        return
    channel = message.forward_from_chat.id
    try:
        chat   = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ I'm not an admin there yet. Make me admin and try again.")
            return
        await state.update_data(source=chat.id)
        src_name = await get_chat_name(chat.id)
        await message.answer(
            f"✅ *Source set:* _{src_name}_\n\n{STEP2_TEXT}",
            parse_mode="Markdown"
        )
        await state.set_state(RuleState.Waiting_destination)
    except:
        await message.answer("❌ Invalid channel or I can't access it.")


@dp.message(RuleState.Waiting_destination)
async def get_destination(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() == "/done":
        data = await state.get_data()
        source_id    = data.get("source")
        destinations = data.get("destinations", [])
        if not source_id or not destinations:
            await message.answer("❌ *Setup incomplete.* Need a source and at least one destination.", parse_mode="Markdown")
            await state.clear()
            return
        save_rule(message.from_user.id, source_id, ",".join(map(str, destinations)))
        await state.clear()
        await message.answer(
            "🎉 *Rule created!* Forwarding is now active.\n\nUse the menu to manage your rules.",
            reply_markup=main_menu(), parse_mode="Markdown"
        )
        return

    if message.forward_from_chat:
        channel = message.forward_from_chat.id
        try:
            chat   = await bot.get_chat(channel)
            member = await bot.get_chat_member(chat.id, bot.id)
            if member.status not in ["administrator", "creator"]:
                await message.answer("⚠️ I'm not an admin there. Make me admin first.")
                return
            data = await state.get_data()
            destinations = data.get("destinations", [])
            if channel not in destinations:
                destinations.append(channel)
                await state.update_data(destinations=destinations)
                name = await get_chat_name(channel)
                await message.answer(
                    f"✅ *{name}* added! _{len(destinations)} destination(s)._\n\nForward another or send /done.",
                    parse_mode="Markdown"
                )
            else:
                await message.answer("⚠️ Already added.")
        except:
            await message.answer("❌ Couldn't access that channel.")
    else:
        await message.answer("⚠️ Please forward a post from a channel.")


# ════════════════════════════════════════════════
#   EDIT RULE
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data.startswith("edit_") and c.data[5:].isdigit())
async def edit_rule(call: types.CallbackQuery, state: FSMContext):
    rule_id = int(call.data.split("_")[1])
    cursor.execute(
        "SELECT source_chat_id, destination_chat_ids, filter_types, blacklist_keywords, delay_seconds FROM rules WHERE id=%s AND user_id=%s",
        (rule_id, call.from_user.id)
    )
    row = cursor.fetchone()
    if not row:
        await call.answer("Rule not found", show_alert=True)
        return

    src_id, dst_ids, filter_types, _, delay_seconds = row
    saved_filters = filter_types.split(",") if filter_types else ["all"]
    filter_dict   = {k: (1 if k in saved_filters else 0) for k in ["all", "text", "photo", "video", "audio", "document", "link"]}

    await state.update_data(rule_id=rule_id, destinations=dst_ids.split(","), filters=filter_dict, delay_seconds=delay_seconds or 0)
    await state.set_state(EditRuleState.ChoosingAction)

    src_name = await get_chat_name(int(src_id))
    await call.message.edit_text(edit_menu_text(src_name), reply_markup=edit_menu_keyboard(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda c: c.data == "edit_cancel")
async def edit_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_to_rules(call)
    await call.answer()


@dp.callback_query(lambda c: c.data == "edit_done")
async def edit_done(call: types.CallbackQuery, state: FSMContext):
    data         = await state.get_data()
    rule_id      = data.get("rule_id")
    destinations = data.get("destinations", [])
    if not destinations:
        await call.answer("❌ A rule needs at least one destination.", show_alert=True)
        return
    filters      = data.get("filters", {"all": 1})
    enabled      = [k for k, v in filters.items() if v == 1]
    delay        = data.get("delay_seconds", 0)
    cursor.execute(
        "UPDATE rules SET destination_chat_ids=%s, filter_types=%s, delay_seconds=%s WHERE id=%s AND user_id=%s",
        (",".join(destinations), ",".join(enabled), delay, rule_id, call.from_user.id)
    )
    db.commit()
    await state.clear()
    await edit_to_rules(call)
    await call.answer("✅ Rule saved!")


@dp.callback_query(lambda c: c.data == "edit_back")
async def edit_back(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data.get("rule_id")
    await edit_to_edit_menu(call, call.from_user.id, rule_id, state)
    await call.answer()


# ── Add destination ──────────────────────────────

@dp.callback_query(lambda c: c.data == "edit_add")
async def edit_add(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.AddingDestination)
    await call.message.edit_text(
        "➕ *Add Destination Channel*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Forward a post from each channel you want to add.\n\n"
        "Tap *Done* when finished.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Done", callback_data="edit_done")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="edit_back")],
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(EditRuleState.AddingDestination)
async def add_destination_msg(message: types.Message, state: FSMContext):
    if not message.forward_from_chat:
        await message.answer("⚠️ Please forward a post from a channel.")
        return
    channel_id   = message.forward_from_chat.id
    data         = await state.get_data()
    destinations = data.get("destinations", [])
    if str(channel_id) in destinations:
        await message.answer("⚠️ Already in the list.")
        return
    destinations.append(str(channel_id))
    await state.update_data(destinations=destinations)
    name = await get_chat_name(channel_id)
    await message.answer(f"✅ *{name}* added! _{len(destinations)} total._\n\nForward another or tap *Done*.", parse_mode="Markdown")


# ── Remove destination ───────────────────────────

@dp.callback_query(EditRuleState.ChoosingAction, lambda c: c.data == "edit_remove")
async def edit_remove(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.RemovingDestination)
    await _render_remove_ui(call, state)
    await call.answer()


async def _render_remove_ui(call: types.CallbackQuery, state: FSMContext):
    data         = await state.get_data()
    destinations = data.get("destinations", [])
    kb = []
    for d in destinations:
        name = await get_chat_name(int(d))
        kb.append([InlineKeyboardButton(text=f"➖ {name}", callback_data=f"remove_{d}")])
    kb.append([
        InlineKeyboardButton(text="✅ Done", callback_data="edit_done"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="edit_back"),
    ])
    await call.message.edit_text(
        "➖ *Remove Destination*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Tap a channel below to remove it:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )


@dp.callback_query(EditRuleState.RemovingDestination, lambda c: c.data.startswith("remove_"))
async def remove_destination(call: types.CallbackQuery, state: FSMContext):
    remove_id    = call.data.split("_")[1]
    data         = await state.get_data()
    destinations = data.get("destinations", [])
    if remove_id in destinations:
        destinations.remove(remove_id)
        await state.update_data(destinations=destinations)
    await _render_remove_ui(call, state)
    await call.answer("❌ Removed")


# ════════════════════════════════════════════════
#   FILTERS
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "edit_filters")
async def edit_filters(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    filters = data.get("filters", {"all": 1, "text": 0, "photo": 0, "video": 0, "audio": 0, "document": 0, "link": 0})
    await state.update_data(filters=filters)
    await call.message.edit_text(FILTER_TEXT, reply_markup=filter_keyboard(filters), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda c: c.data.startswith("filter_") and c.data not in ("filter_back", "filter_save"))
async def toggle_filter(call: types.CallbackQuery, state: FSMContext):
    key     = call.data.replace("filter_", "")
    data    = await state.get_data()
    filters = data.get("filters", {"all": 1, "text": 0, "photo": 0, "video": 0, "audio": 0, "document": 0, "link": 0})
    if key == "all":
        filters = {k: 0 for k in filters}
        filters["all"] = 1
    else:
        filters["all"] = 0
        filters[key]   = 0 if filters.get(key) else 1
        if not any(filters.values()):
            filters["all"] = 1
    await state.update_data(filters=filters)
    await call.message.edit_reply_markup(reply_markup=filter_keyboard(filters))
    await call.answer()


@dp.callback_query(lambda c: c.data == "filter_back")
async def filter_back(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data.get("rule_id")
    await edit_to_edit_menu(call, call.from_user.id, rule_id, state)
    await call.answer()


@dp.callback_query(lambda c: c.data == "filter_save")
async def filter_save(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data["rule_id"]
    filters = data.get("filters", {"all": 1})
    enabled = [k for k, v in filters.items() if v == 1]
    cursor.execute("UPDATE rules SET filter_types=%s WHERE id=%s AND user_id=%s", (",".join(enabled), rule_id, call.from_user.id))
    db.commit()
    await edit_to_edit_menu(call, call.from_user.id, rule_id, state)
    await call.answer("✅ Filters saved")


# ════════════════════════════════════════════════
#   BLACKLIST
# ════════════════════════════════════════════════

@dp.callback_query(lambda c: c.data == "edit_blacklist")
async def edit_blacklist(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data["rule_id"]
    cursor.execute("SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s", (rule_id, call.from_user.id))
    row     = cursor.fetchone()
    current = row[0] if row and row[0] else ""
    await call.message.edit_text(blacklist_text(current), reply_markup=blacklist_keyboard(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(lambda c: c.data == "bl_add")
async def blacklist_add_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.AddingBlacklist)
    await call.message.edit_text(
        "➕ *Add Blacklist Keywords*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Send keywords separated by commas.\n\n"
        "Example: `spam, scam, crypto, prize`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="edit_blacklist")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(EditRuleState.AddingBlacklist)
async def add_blacklist_keywords(message: types.Message, state: FSMContext):
    data      = await state.get_data()
    rule_id   = data["rule_id"]
    new_words = [w.strip().lower() for w in message.text.split(",") if w.strip()]
    cursor.execute("SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s", (rule_id, message.from_user.id))
    row      = cursor.fetchone()
    existing = row[0].split(",") if row and row[0] else []
    updated  = list(set(existing + new_words))
    cursor.execute("UPDATE rules SET blacklist_keywords=%s WHERE id=%s AND user_id=%s", (",".join(updated), rule_id, message.from_user.id))
    db.commit()
    await edit_to_edit_menu(message, message.from_user.id, rule_id, state)


@dp.callback_query(lambda c: c.data == "bl_remove")
async def blacklist_remove_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditRuleState.RemovingBlacklist)
    await call.message.edit_text(
        "➖ *Remove Blacklist Keywords*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Send keywords to remove, separated by commas.\n\n"
        "Example: `crypto, prize`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="edit_blacklist")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(EditRuleState.RemovingBlacklist)
async def remove_blacklist_keywords(message: types.Message, state: FSMContext):
    data         = await state.get_data()
    rule_id      = data["rule_id"]
    remove_words = [w.strip().lower() for w in message.text.split(",") if w.strip()]
    cursor.execute("SELECT blacklist_keywords FROM rules WHERE id=%s AND user_id=%s", (rule_id, message.from_user.id))
    row = cursor.fetchone()
    if not row or not row[0]:
        await message.answer("⚠️ No keywords found.")
        return
    existing = row[0].split(",")
    updated  = [w for w in existing if w not in remove_words]
    cursor.execute("UPDATE rules SET blacklist_keywords=%s WHERE id=%s AND user_id=%s", (",".join(updated), rule_id, message.from_user.id))
    db.commit()
    await edit_to_edit_menu(message, message.from_user.id, rule_id, state)


@dp.callback_query(lambda c: c.data == "bl_back")
async def blacklist_back(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data.get("rule_id")
    await edit_to_edit_menu(call, call.from_user.id, rule_id, state)
    await call.answer()


# ════════════════════════════════════════════════
#   DELAY
# ════════════════════════════════════════════════

@dp.callback_query(EditRuleState.ChoosingAction, lambda c: c.data == "edit_delay")
async def edit_delay(call: types.CallbackQuery, state: FSMContext):
    data          = await state.get_data()
    current_delay = data.get("delay_seconds", 0)
    await state.set_state(DelayState.WaitingDelay)
    await call.message.edit_text(
        "⏱ *Set Forwarding Delay*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"Current delay: *{current_delay} seconds*\n\n"
        "Send the number of seconds to wait\n"
        "before forwarding each message.\n\n"
        "Examples:\n"
        "  `0` — forward instantly\n"
        "  `30` — 30 seconds\n"
        "  `300` — 5 minutes\n"
        "  `3600` — 1 hour\n\n"
        "⚠️ _Max: 86400 seconds (24 hours)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Cancel", callback_data="delay_cancel")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(DelayState.WaitingDelay)
async def receive_delay(message: types.Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    if not text.isdigit():
        await message.answer("❌ Please send a valid number. Example: `60`", parse_mode="Markdown")
        return
    seconds = int(text)
    if seconds > 86400:
        await message.answer("❌ Max is *86400* (24 hours).", parse_mode="Markdown")
        return
    await state.update_data(delay_seconds=seconds)
    data    = await state.get_data()
    rule_id = data.get("rule_id")
    await edit_to_edit_menu(message, message.from_user.id, rule_id, state)


@dp.callback_query(DelayState.WaitingDelay, lambda c: c.data == "delay_cancel")
async def delay_cancel(call: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    rule_id = data.get("rule_id")
    await edit_to_edit_menu(call, call.from_user.id, rule_id, state)
    await call.answer()


# ════════════════════════════════════════════════
#   CATCH-ALLS
# ════════════════════════════════════════════════

@dp.callback_query()
async def noop_handler(call: types.CallbackQuery):
    await call.answer()


@dp.message()
async def any_message(message: types.Message):
    if not get_user(message.from_user.id):
        save_user(message.from_user.id, message.from_user.first_name, message.from_user.username)
    await message.answer("👋 Use /start to open the menu.", reply_markup=main_menu())


# ════════════════════════════════════════════════
#   FORWARDING ENGINE
# ════════════════════════════════════════════════

def get_message_type(msg: types.Message):
    if msg.text and "http" in msg.text: return "link"
    if msg.text:     return "text"
    if msg.photo:    return "photo"
    if msg.video:    return "video"
    if msg.audio:    return "audio"
    if msg.document: return "document"
    return None


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', ' ', text)


def contains_blacklist(text: str, blacklist_string: str) -> bool:
    if not text or not blacklist_string:
        return False
    original   = text.lower()
    normalized = normalize_text(text)
    for word in [w.strip().lower() for w in blacklist_string.split(",") if w.strip()]:
        if re.search(r'\b' + re.escape(word) + r'\b', original):
            return True
        if word in normalized.replace(" ", ""):
            return True
    return False


@dp.channel_post()
async def forward_from_source(message: types.Message):
    cursor.execute(
        "SELECT destination_chat_ids, filter_types, blacklist_keywords, delay_seconds FROM rules WHERE source_chat_id=%s AND is_active=1",
        (message.chat.id,)
    )
    msg_type     = get_message_type(message)
    text_content = message.text or message.caption or ""
    for dest_string, filter_types, blacklist_keywords, delay_seconds in cursor.fetchall():
        allowed = filter_types.split(",")
        if "all" not in allowed and msg_type not in allowed:
            continue
        if contains_blacklist(text_content, blacklist_keywords):
            continue
        if delay_seconds and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        for dest_id in dest_string.split(","):
            try:
                sent = await message.copy_to(int(dest_id))
                cursor.execute(
                    "INSERT INTO message_map (source_chat_id, source_message_id, destination_chat_id, destination_message_id) VALUES (%s,%s,%s,%s)",
                    (message.chat.id, message.message_id, int(dest_id), sent.message_id)
                )
            except:
                pass


@dp.edited_channel_post()
async def handle_edit(message: types.Message):
    cursor.execute(
        "SELECT destination_chat_id, destination_message_id FROM message_map WHERE source_chat_id=%s AND source_message_id=%s",
        (message.chat.id, message.message_id)
    )
    rows = cursor.fetchall()
    if not rows:
        return
    new_text = message.text or message.caption
    for dest_chat, dest_msg in rows:
        try:
            if new_text:
                if message.text:
                    await bot.edit_message_text(chat_id=dest_chat, message_id=dest_msg, text=new_text)
                else:
                    await bot.edit_message_caption(chat_id=dest_chat, message_id=dest_msg, caption=new_text)
            else:
                await bot.delete_message(chat_id=dest_chat, message_id=dest_msg)
        except:
            pass


# ════════════════════════════════════════════════
#   MAIN
# ════════════════════════════════════════════════

async def main():
    await dp.start_polling(bot)

asyncio.run(main())