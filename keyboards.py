from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Select Source Channel", callback_data="source")],
        [InlineKeyboardButton(text="📤 Select Destination Channels", callback_data="destination")]
    ])

def save_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Save Rules", callback_data="save")]
    ])
