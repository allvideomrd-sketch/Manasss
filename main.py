import os
import json
import asyncio
import smtplib
import socket
from email.mime.text import MIMEText
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
#  CONFIGURATION & DATA PATHS
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8558626927:AAFV3wIH0flAirKep8N10Em8T0TBC6pNCpY")
EMAIL_USER = os.getenv("EMAIL_USER", "alphacopyright11@gmail.com")
EMAIL_PASS = os.getenv("EMAIL_PASS", "xqmwtomayodnmzrj")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1908783570"))  # Replace with your Telegram ID

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
EMAILS_FILE = os.path.join(DATA_DIR, "emails.json")
PREMIUM_FILE = os.path.join(DATA_DIR, "premium.json")
OWNERS_FILE = os.path.join(DATA_DIR, "owners.json")
CREDITS_FILE = os.path.join(DATA_DIR, "credits.json")

# Dynamic state variables
emails = []
owners = []
premium_users = set()
user_credits = {}

# Session states tracking
user_session = {}
user_state = {}

# ============================================================
#  DATA LOAD / SAVE HELPERS
# ============================================================
def ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(file_path, default_val):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val

def save_json(file_path, data):
    ensure_dir()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_all_data():
    global emails, owners, premium_users, user_credits
    default_emails = [
        "abuse@telegram.org", "support@telegram.org", "report@telegram.org",
        "security@telegram.org", "developers@telegram.org", "support@stel.com",
        "abuse@stel.com", "reclaim@telegram.org", "copyright@telegram.org",
        "complaints@telegram.org", "legal@telegram.org", "ios@telegram.org",
        "android@telegram.org", "support@kucoin.com", "web@telegram.org",
        "api@telegram.org", "feedback@telegram.org", "spam@telegram.org",
        "scam@telegram.org", "moderator@telegram.org", "admin@telegram.org",
        "noreply@telegram.org", "sms@telegram.org", "support@group-ib.com",
        "response@cert-gib.com"
    ]
    emails = load_json(EMAILS_FILE, default_emails)
    
    # Auto-load owners & force ensure current ADMIN_ID is included
    loaded_owners = load_json(OWNERS_FILE, [ADMIN_ID])
    if ADMIN_ID not in loaded_owners:
        loaded_owners.append(ADMIN_ID)
    owners = loaded_owners
    
    premium_arr = load_json(PREMIUM_FILE, [])
    premium_users = set(premium_arr)
    user_credits = load_json(CREDITS_FILE, {})

def save_all_data():
    save_json(EMAILS_FILE, emails)
    save_json(OWNERS_FILE, owners)
    save_json(PREMIUM_FILE, list(premium_users))
    save_json(CREDITS_FILE, user_credits)

# ============================================================
#  HELPER FUNCTIONS (UNLIMITED OWNER CREDITS)
# ============================================================
def is_owner(user_id: int) -> bool:
    return int(user_id) in owners

def is_premium(user_id: int) -> bool:
    return int(user_id) in premium_users or is_owner(user_id)

def get_credits(user_id: int):
    if is_owner(user_id):
        return "∞ (Unlimited)"
    return user_credits.get(str(user_id), 0)

def add_credits(user_id: int, amount: int):
    uid = str(user_id)
    user_credits[uid] = user_credits.get(uid, 0) + amount

def use_credit(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    
    uid = str(user_id)
    if user_credits.get(uid, 0) > 0:
        user_credits[uid] -= 1
        return True
    return False

# ============================================================
#  EMAIL LOGIC (FIXED NON-BLOCKING WITH TIMEOUT)
# ============================================================
def generate_email_content(data: dict) -> str:
    return data.get('description', '')

def _send_mail_sync(dest, subject, content):
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Scam Reporter <{EMAIL_USER}>"
    msg["To"] = dest

    # Added 10 seconds strict timeout to prevent Render thread hanging
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [dest], msg.as_string())

async def send_email_reports(data: dict, loop: int = 1, delay: int = 0, target_emails: list = None):
    content = generate_email_content(data)
    recipients = target_emails if target_emails else emails
    results = []

    subject = f"[SCAM REPORT] {data.get('username', 'Unknown')}{' - CHANNEL' if data.get('type') == 'channel' else ''}"

    for i in range(loop):
        for dest in recipients:
            try:
                # Execution pushed completely to background executor
                await asyncio.to_thread(_send_mail_sync, dest, subject, content)
                results.append({"dest": dest, "loop": i + 1, "status": "OK"})
            except Exception as err:
                results.append({"dest": dest, "loop": i + 1, "status": "FAIL", "error": str(err)})

            if delay > 0 and (i < loop - 1 or dest != recipients[-1]):
                await asyncio.sleep(delay)

    return results

# ============================================================
#  KEYBOARDS
# ============================================================
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Report Scam", callback_data="report")],
        [InlineKeyboardButton("🏷️ Scam Tag (Premium)", callback_data="scam_tag")],
        [InlineKeyboardButton("📧 Manage Emails", callback_data="manage_emails")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"), InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👑 Add Owner", callback_data="addowner"), InlineKeyboardButton("👑 Del Owner", callback_data="delowner")],
        [InlineKeyboardButton("⭐ Premium", callback_data="premium"), InlineKeyboardButton("💰 Add Credit", callback_data="addcredit"), InlineKeyboardButton("🪙 Credit", callback_data="credit")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Send", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_after_report_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Report Again", callback_data="report")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_email_manage_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Email", callback_data="add_email")],
        [InlineKeyboardButton("➖ Remove Email", callback_data="remove_email")],
        [InlineKeyboardButton("📋 View Emails", callback_data="list_emails")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ============================================================
#  COMMAND & ACTION HANDLERS
# ============================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_session.pop(user_id, None)
    user_state.pop(user_id, None)
    load_all_data()

    start_message = (
        "<b>🚨 TELEGRAM SCAM REPORT BOT</b>\n\n"
        "Send scam reports directly to multiple security support channels.\n\n"
        "📌 <b>How to use:</b>\n"
        "• Click the menu buttons below, or\n"
        "• Use command: /report &lt;username&gt;\n\n"
        "📋 <b>Available Commands:</b>\n"
        "• /report &lt;username&gt; – Start a new report\n"
        "• /menu – Show main menu\n"
        "• /batal – Cancel current process\n"
        "• /help – View help\n"
        "• /status – Check bot status\n"
        "• /premium – Check premium status\n"
        "• /credit – Check your remaining credits\n"
        "• /addemail &lt;email&gt; – Add email (Owner)\n"
        "• /removeemail &lt;email&gt; – Remove email (Owner)\n"
        "• /listemails – View email list (Owner)\n"
        "• /addowner &lt;id&gt; – Add owner (Owner)\n"
        "• /delowner &lt;id&gt; – Remove owner (Owner)\n"
        "• /addprem &lt;id&gt; – Add premium user (Owner)\n"
        "• /delprem &lt;id&gt; – Remove premium user (Owner)\n"
        "• /addcredit &lt;id&gt; &lt;amount&gt; – Add credits (Owner)\n\n"
        "Select an option below:"
    )
    await update.message.reply_html(start_message, reply_markup=get_main_menu())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_session.pop(user_id, None)
    user_state.pop(user_id, None)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("<b>🏠 Main Menu</b>", parse_mode="HTML", reply_markup=get_main_menu())
    else:
        await update.message.reply_html("<b>🏠 Main Menu</b>", reply_markup=get_main_menu())

async def batal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_session or user_id in user_state:
        user_session.pop(user_id, None)
        user_state.pop(user_id, None)
        await update.message.reply_text("❌ Process cancelled.")
    else:
        await update.message.reply_text("⚠️ No active process running.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>📖 Bot Assistance</b>\n\n"
        "<b>📌 Features Available:</b>\n\n"
        "<b>📝 Report Scam</b>\n"
        "Report Telegram scam accounts directly to security channels.\n\n"
        "<b>🏷️ Scam Tag (Premium)</b>\n"
        "Generate a official scam warning tag for channels (Premium / Credit required).\n\n"
        "<b>📧 Manage Emails</b> (Owner)\n"
        "Add or remove destination target emails.\n\n"
        "<b>👑 Owner Panel</b> (Owner)\n"
        "• Manage Owners\n"
        "• Manage Premium Users\n"
        "• Add Credits\n\n"
        "<b>🪙 Credits</b>\n"
        "Check your available credit balance.\n\n"
        "<b>📊 Status</b>\n"
        "Check overall bot system metrics.\n\n"
        "⚠️ For inquiries, contact @GrenTzy."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_html(help_text)
    else:
        await update.message.reply_html(help_text)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_prem = is_premium(user_id)
    credits_val = get_credits(user_id)
    
    msg = (
        f"<b>🟢 Bot Status</b>\n"
        f"✅ Online\n"
        f"📧 Sender Email: {EMAIL_USER}\n"
        f"📤 Target List: {len(emails)} emails\n"
        f"📊 Active Sessions: {len(user_session)}\n"
        f"👑 Premium Status: {'✅ Active' if is_prem else '❌ Inactive'}\n"
        f"🪙 Credits: {credits_val}"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="status")]])
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_html(msg, reply_markup=kb)

async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_prem = is_premium(user_id)
    credits_val = get_credits(user_id)

    msg = f"<b>👑 Premium Active!</b> Feature unlocked: Scam Tag Generator. Credits: {credits_val}" if is_prem else f"<b>❌ Not Premium.</b> Credits: {credits_val}. Contact owner to acquire premium status or credits."
    
    kb_list = [[InlineKeyboardButton("🏠 Menu", callback_data="menu")]]
    if not is_prem:
        kb_list.insert(0, [InlineKeyboardButton("📞 Contact Owner", url="https://t.me/NullQor")])

    kb = InlineKeyboardMarkup(kb_list)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_html(msg, reply_markup=kb)
    else:
        await update.message.reply_html(msg, reply_markup=kb)

async def credit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = f"🪙 Your Credits: {get_credits(user_id)}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu")]])
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg, reply_markup=kb)

# ============================================================
#  REPORT PROCESS HANDLERS
# ============================================================
async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    username_or_name = f"@{user.username}" if user.username else user.first_name

    user_session.pop(user_id, None)

    args = context.args if context.args else []
    username_arg = " ".join(args).strip() if args else None

    if username_arg:
        user_session[user_id] = {
            "step": "type",
            "data": {"reporter": username_or_name, "username": username_arg}
        }
        msg = "☠️ Select scam target type:\n<code>bot</code>, <code>channel</code>, <code>group</code>, <code>user</code>, <code>phishing</code>"
    else:
        user_session[user_id] = {
            "step": "username",
            "data": {"reporter": username_or_name}
        }
        msg = "📱 Enter <b>username</b> or ID of the scam target (e.g. @scammer_bot):"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_html(msg)
    else:
        await update.message.reply_html(msg)

async def scam_tag_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = update.effective_user
    username_or_name = f"@{user.username}" if user.username else user.first_name

    if not is_premium(user_id):
        if not use_credit(user_id):
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="menu")]])
            return await query.message.reply_html(
                "<b>⛔ Premium Feature.</b>\nUse /premium to check status, or contact admin to acquire access.",
                reply_markup=kb
            )
        else:
            save_json(CREDITS_FILE, user_credits)

    user_session.pop(user_id, None)
    user_session[user_id] = {
        "step": "scam_tag_username",
        "data": {"reporter": username_or_name}
    }
    await query.message.reply_html("🏷️ Enter target <b>channel username</b> (e.g. @channelname):")

# ============================================================
#  OWNER & EMAIL MANAGEMENT HANDLERS
# ============================================================
async def manage_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        return await query.answer("⛔ Owner restricted area.", show_alert=True)
    await query.answer()
    await query.message.delete()
    await query.message.reply_html("<b>📧 Target Email Management</b>", reply_markup=get_email_manage_keyboard())

async def owner_action_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return await query.answer("⛔ Owner restricted area.", show_alert=True)
    
    await query.answer()
    action = query.data

    prompts = {
        "addowner": "📌 Send User ID to promote as Owner.\nExample: <code>123456789</code>",
        "delowner": "📌 Send User ID to demote from Owner.\nExample: <code>123456789</code>",
        "addprem": "📌 Send User ID to grant Premium access.\nExample: <code>123456789</code>",
        "delprem": "📌 Send User ID to revoke Premium access.\nExample: <code>123456789</code>",
        "addcredit": "📌 Send User ID and credit amount.\nFormat: <code>&lt;user_id&gt; &lt;amount&gt;</code>\nExample: <code>123456789 10</code>",
        "add_email": "📧 Send email address to add (e.g. target@domain.com)",
        "remove_email": "📧 Send email address to remove"
    }

    if action in ["add_email", "remove_email"]:
        user_session[user_id] = {"step": action}
        await query.message.reply_text(prompts[action])
    else:
        user_state[user_id] = {"action": action}
        await query.message.reply_html(prompts[action])

async def list_emails_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        if update.callback_query:
            return await update.callback_query.answer("⛔ Owner restricted area.", show_alert=True)
        return await update.message.reply_text("⛔ Owner restricted area.")

    load_all_data()
    email_list = "\n".join([f"{i+1}. {e}" for i, e in enumerate(emails)]) if emails else "Empty"
    msg = f"<b>📧 Target Email List ({len(emails)})</b>\n{email_list}"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_html(msg)
    else:
        await update.message.reply_html(msg)

# ============================================================
#  CALLBACK QUERY SELECT & CONFIRM
# ============================================================
async def handle_email_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = user_session.get(user_id)

    if not session or session.get("step") != "select_email":
        return await query.answer("Invalid session.")

    data = query.data
    if data == "select_email_all":
        session["selectedEmails"] = list(emails)
        session["step"] = "loop"
        await query.answer("✅ Sending to all target emails")
        await query.message.delete()
        await query.message.reply_text("🔁 How many times to repeat sending (loop count)? (Number)")
    elif data.startswith("select_email_"):
        idx = int(data.split("_")[2])
        if idx < len(emails):
            session["selectedEmails"] = [emails[idx]]
            session["step"] = "loop"
            await query.answer(f"✅ Selected: {emails[idx]}")
            await query.message.delete()
            await query.message.reply_text("🔁 How many times to repeat sending (loop count)? (Number)")

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    session = user_session.get(user_id)

    if query.data == "confirm_no":
        user_session.pop(user_id, None)
        await query.message.delete()
        return await query.message.reply_text("❌ Action cancelled.", reply_markup=get_after_report_keyboard())

    if not session or session.get("step") != "confirm":
        return await query.message.reply_text("⚠️ Invalid session. Please start again with /report")

    status_msg = await query.message.reply_text("⏳ Processing email transmission...")

    data = session["data"]
    loop = session["loop"]
    delay = session["delay"]
    target_emails = session.get("selectedEmails")

    results = await send_email_reports(data, loop, delay, target_emails)
    total = len(results)
    success = len([r for r in results if r["status"] == "OK"])
    failed = total - success

    msg = f"<b>📤 Execution Summary</b>\n✅ {success} Successful\n❌ {failed} Failed\n📊 Total Transmissions: {total}\n\n"
    if failed > 0:
        msg += "<b>Error Preview:</b>\n"
        errors = [r for r in results if r["status"] == "FAIL"][:3]
        for e in errors:
            msg += f"- {e['dest']}: {e['error'][:50]}...\n"

    msg += f"\nScam report for <b>{data.get('username')}</b> has been processed."
    await status_msg.edit_text(msg, parse_mode="HTML", reply_markup=get_after_report_keyboard())
    print(f"[LOG] {data.get('reporter')} -> {data.get('username')} ({success}/{total}) loop={loop} delay={delay}")
    user_session.pop(user_id, None)

# ============================================================
#  TEXT MESSAGE PROCESSOR
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id in user_state:
        state_data = user_state.pop(user_id)
        action = state_data["action"]

        if action in ["addowner", "delowner", "addprem", "delprem"]:
            if not text.isdigit():
                return await update.message.reply_text("❌ Invalid User ID. Please provide numeric format.")
            target_id = int(text)

            if action == "addowner":
                if target_id in owners:
                    return await update.message.reply_text("⚠️ User ID is already an Owner.")
                owners.append(target_id)
                save_all_data()
                return await update.message.reply_text(f"✅ User ID {target_id} is now an Owner.")

            elif action == "delowner":
                if target_id == ADMIN_ID:
                    return await update.message.reply_text("❌ Cannot remove primary bot owner.")
                if target_id not in owners:
                    return await update.message.reply_text("❌ User ID is not an Owner.")
                owners.remove(target_id)
                save_all_data()
                return await update.message.reply_text(f"✅ User ID {target_id} demoted from Owner.")

            elif action == "addprem":
                if target_id in premium_users:
                    return await update.message.reply_text("⚠️ User ID is already Premium.")
                premium_users.add(target_id)
                save_all_data()
                return await update.message.reply_text(f"✅ User ID {target_id} granted Premium status.")

            elif action == "delprem":
                if target_id not in premium_users:
                    return await update.message.reply_text("❌ User ID is not Premium.")
                premium_users.remove(target_id)
                save_all_data()
                return await update.message.reply_text(f"✅ User ID {target_id} removed from Premium.")

        elif action == "addcredit":
            parts = text.split()
            if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
                return await update.message.reply_text("❌ Format: <user_id> <amount>")
            target_id = int(parts[0])
            amount = int(parts[1])
            if amount <= 0:
                return await update.message.reply_text("❌ Amount must be greater than 0.")
            add_credits(target_id, amount)
            save_all_data()
            return await update.message.reply_text(f"✅ Added {amount} credits to ID {target_id}. Current total: {get_credits(target_id)}")

    session = user_session.get(user_id)
    if not session:
        return

    step = session.get("step")

    if step == "add_email":
        if not is_owner(user_id):
            return await update.message.reply_text("⛔ Owner restricted area.")
        if "@" not in text:
            return await update.message.reply_text("❌ Invalid email format.")
        if text in emails:
            return await update.message.reply_text("⚠️ Email already exists in list.")
        emails.append(text)
        save_all_data()
        user_session.pop(user_id, None)
        return await update.message.reply_text(f"✅ Email {text} successfully added.")

    if step == "remove_email":
        if not is_owner(user_id):
            return await update.message.reply_text("⛔ Owner restricted area.")
        if text not in emails:
            return await update.message.reply_text("❌ Email not found in list.")
        emails.remove(text)
        save_all_data()
        user_session.pop(user_id, None)
        return await update.message.reply_text(f"✅ Email {text} removed.")

    if step == "scam_tag_username":
        tag = (
            f"<b>🏷️ SCAM CHANNEL TAG — GRENXHARIMAU EDITION</b>\n"
            f"Channel  : {text}\n"
            f"Reporter : {session['data']['reporter']}\n"
            f"Date     : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"⚠️ WARNING: This channel has been identified as a scam!\n"
            f"Report immediately! #GrenXHarimau #AntiScam"
        )
        await update.message.reply_html(tag)
        await update.message.reply_text("✅ Scam tag generated successfully!", reply_markup=get_after_report_keyboard())
        user_session.pop(user_id, None)
        return

    if step == "username":
        session["data"]["username"] = text
        session["step"] = "type"
        return await update.message.reply_html("☠️ Select target type:\n<code>bot</code>, <code>channel</code>, <code>group</code>, <code>user</code>, <code>phishing</code>")

    if step == "type":
        valid_types = ["bot", "channel", "group", "user", "phishing"]
        if text.lower() not in valid_types:
            return await update.message.reply_text("❌ Invalid target type. Choose from: bot, channel, group, user, phishing")
        session["data"]["type"] = text.lower()
        session["step"] = "description"
        return await update.message.reply_text("📝 Provide detailed description of the scam:")

    if step == "description":
        session["data"]["description"] = text
        session["step"] = "select_email"

        kb_list = [[InlineKeyboardButton(f"{i+1}. {e}", callback_data=f"select_email_{i}")] for i, e in enumerate(emails)]
        kb_list.append([InlineKeyboardButton("📧 Send to All Emails", callback_data="select_email_all")])
        kb_list.append([InlineKeyboardButton("🔙 Cancel", callback_data="confirm_no")])

        return await update.message.reply_html("<b>📧 Select destination target email:</b>", reply_markup=InlineKeyboardMarkup(kb_list))

    if step == "loop":
        if not text.isdigit() or int(text) < 1:
            return await update.message.reply_text("❌ Please enter a positive number.")
        session["loop"] = int(text)
        session["step"] = "delay"
        return await update.message.reply_text("⏱️ Delay between sending (in seconds):")

    if step == "delay":
        if not text.isdigit() or int(text) < 0:
            return await update.message.reply_text("❌ Please enter a valid non-negative number.")
        session["delay"] = int(text)
        session["step"] = "confirm"

        data = session["data"]
        selected = ", ".join(session.get("selectedEmails", ["All"]))
        desc = data["description"]
        desc_short = desc[:100] + ("..." if len(desc) > 100 else "")

        summary = (
            f"<b>📋 Report Summary</b>\n"
            f"Username   : {data['username']}\n"
            f"Type       : {data['type']}\n"
            f"Description: {desc_short}\n"
            f"Recipients : {selected}\n"
            f"Loop Count : {session['loop']}\n"
            f"Delay      : {session['delay']} second(s)\n\n"
            f"Click the button below to execute."
        )
        return await update.message.reply_html(summary, reply_markup=get_confirm_keyboard())

# ============================================================
#  MAIN APPLICATION SETUP
# ============================================================
def main():
    load_all_data()
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("batal", batal_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("credit", credit_cmd))
    app.add_handler(CommandHandler("report", report_start))
    app.add_handler(CommandHandler("listemails", list_emails_handler))

    # Callbacks
    app.add_handler(CallbackQueryHandler(menu_cmd, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(report_start, pattern="^report$"))
    app.add_handler(CallbackQueryHandler(scam_tag_start, pattern="^scam_tag$"))
    app.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(status_cmd, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(premium_cmd, pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(credit_cmd, pattern="^credit$"))
    app.add_handler(CallbackQueryHandler(manage_emails, pattern="^manage_emails$"))
    app.add_handler(CallbackQueryHandler(list_emails_handler, pattern="^list_emails$"))
    
    # Dynamic Admin/Owner Trigger Callbacks
    app.add_handler(CallbackQueryHandler(owner_action_trigger, pattern="^(addowner|delowner|addprem|delprem|addcredit|add_email|remove_email)$"))
    app.add_handler(CallbackQueryHandler(handle_email_selection, pattern="^select_email_"))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern="^confirm_(yes|no)$"))

    # Text Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
