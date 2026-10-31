import os
import sqlite3
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB = "anime.db"

NAME, VIDEO = range(2)


def db():
    return sqlite3.connect(DB)


def init_db():
    with db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS anime ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, "
            "file_id TEXT NOT NULL, "
            "file_type TEXT NOT NULL)"
        )


def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Anime nomini yuboring.")


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    with db() as c:
        rows = c.execute("SELECT name, file_id, file_type FROM anime").fetchall()
    found = [r for r in rows if query in r[0].lower()]
    if not found:
        await update.message.reply_text("Afsuski, topilmadi. Boshqa nom yozib ko'ring.")
        return
    for name, file_id, file_type in found[:10]:
        if file_type == "video":
            await update.message.reply_video(file_id, caption=name)
        else:
            await update.message.reply_document(file_id, caption=name)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Siz admin emassiz.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Anime qo'shish", callback_data="add")],
            [InlineKeyboardButton("📋 Ro'yxat / O'chirish", callback_data="list")],
        ]
    )
    await update.message.reply_text("Admin panel:", reply_markup=keyboard)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    q = update.callback_query
    if q:
        await q.answer()
        message = q.message
    else:
        message = update.message
    await message.reply_text("Anime nomini yozing (bekor qilish: /cancel):")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Endi videoni yuboring:")
    return VIDEO


async def get_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.video:
        file_id, file_type = msg.video.file_id, "video"
    elif msg.document:
        file_id, file_type = msg.document.file_id, "document"
    else:
        await msg.reply_text("Iltimos, video yuboring.")
        return VIDEO
    name = context.user_data.get("name", "Nomsiz")
    with db() as c:
        c.execute(
            "INSERT INTO anime (name, file_id, file_type) VALUES (?, ?, ?)",
            (name, file_id, file_type),
        )
    await msg.reply_text(f"✅ Saqlandi: {name}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(update):
        return
    with db() as c:
        rows = c.execute("SELECT id, name FROM anime").fetchall()
    if not rows:
        await q.message.reply_text("Baza bo'sh.")
        return
    buttons = [
        [InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_{id_}")]
        for id_, name in rows[:50]
    ]
    await q.message.reply_text(
        "O'chirish uchun bosing:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(update):
        return
    item_id = int(q.data.split("_")[1])
    with db() as c:
        c.execute("DELETE FROM anime WHERE id = ?", (item_id,))
    await q.message.reply_text("🗑 O'chirildi.")


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi")
    init_db()
    app = Application.builder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_start, pattern="^add$"),
            CommandHandler("add", add_start),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            VIDEO: [MessageHandler(filters.VIDEO | filters.Document.ALL, get_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(show_list, pattern="^list$"))
    app.add_handler(CallbackQueryHandler(delete_item, pattern="^del_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    app.run_polling()


if __name__ == "__main__":
    main()
