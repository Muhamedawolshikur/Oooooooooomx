import subprocess
import sys
import os
import time
import zipfile
import json
import threading
from datetime import datetime
import telebot
from telebot import types
from flask import Flask

# ================= FLASK SERVER FOR RENDER =================
app = Flask('')

@app.route('/')
def home():
    return "Xerox Hosting Cloud is Active and Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Start background web server for Render health checks
threading.Thread(target=run_flask, daemon=True).start()

# ================= BOT CONFIGURATION =================
# በGitHub ላይ በግልጽ እንዳይታይ በEnvironment Variables ተደብቋል
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 8700421304       

STORAGE_DIR = "user_files"
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
DATA_FILE = os.path.join(STORAGE_DIR, "users.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f: json.dump({}, f)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ================= GLOBAL STATES =================
users = {}
active_scripts = {}      # user_id -> file_path -> process
logs_store = {}          # user_id -> file_path -> list of logs
START_TIME = datetime.now()

# ================= DATA PERSISTENCE =================
def save_data():
    try:
        with open(DATA_FILE, "w") as f: json.dump(users, f, indent=4)
    except Exception as e: 
        print(f"[ERROR] Database Save Failed: {e}")

def load_data():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                raw_data = json.load(f)
                users.clear()
                for k, v in raw_data.items(): users[int(k)] = v
        except: 
            users = {}

def user_folder(uid):
    path = os.path.join(UPLOAD_DIR, str(uid))
    os.makedirs(path, exist_ok=True)
    return path

# ================= PROFESSIONAL UI BUTTONS =================
def control_buttons(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🌏 Upload Bot"), types.KeyboardButton("📁 My Terminal"))
    markup.row(types.KeyboardButton("🆘 Support"))
    if uid == OWNER_ID:
        markup.row(types.KeyboardButton("👑 Admin Panel"))
    return markup

# ================= SMART BACKGROUND AUTO-RUNNER =================
def run_script_sync(user_id, file_path):
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(file_path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    active_scripts.setdefault(user_id, {})[file_path] = proc
    logs_store.setdefault(user_id, {})[file_path] = []

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            text = line.strip()
            logs_store[user_id][file_path].append(text)
            # Keep only the last 50 lines to optimize memory/RAM
            logs_store[user_id][file_path] = logs_store[user_id][file_path][-50:]
    
    if user_id in active_scripts and file_path in active_scripts[user_id]:
        active_scripts[user_id].pop(file_path, None)

def start_script_thread(user_id, file_path):
    t = threading.Thread(target=run_script_sync, args=(user_id, file_path), daemon=True)
    t.start()

def install_requirements(folder, chat_id, msg_id):
    req_file = os.path.join(folder, "requirements.txt")
    if os.path.exists(req_file):
        try:
            bot.edit_message_text("⚡ Detecting custom requirements... Installing dependencies...", chat_id, msg_id)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            bot.edit_message_text("✅ All custom dependencies successfully compiled!", chat_id, msg_id)
            time.sleep(1)
        except Exception as e:
            bot.edit_message_text(f"⚠️ Dependency Note: Some packages might have skipped or already exist.", chat_id, msg_id)
            time.sleep(1)

# ================= COMMAND HANDLERS =================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    users.setdefault(uid, {"tier": "FREE", "files": []})
    if uid == OWNER_ID: users[uid]["tier"] = "OWNER"
    save_data()

    welcome_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃      🚀 XEROX CLOUD HOSTING      ┃\n"
        "┃    PREMIUM WEB SERVICE v3.0  ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👤 *Account:* {m.from_user.first_name}\n"
        f"🆔 *User ID:* `{uid}`\n"
        f"🎫 *Plan Status:* `{users[uid]['tier']}`\n\n"
        "Welcome to the control center. Use the keyboard buttons below to manage your projects seamlessly."
    )
    bot.send_message(uid, welcome_text, reply_markup=control_buttons(uid), parse_mode="Markdown")

@bot.message_handler(func=lambda m: True, content_types=['text'])
def keyboard_handler(m):
    uid = m.from_user.id
    text = m.text
    user_data = users.setdefault(uid, {"tier": "FREE", "files": []})

    if text == "🌏 Upload Bot":
        bot.reply_to(m, "📤 Please send your script as a document. Supported formats: `.py` or packed `.zip`.")
    
    elif text == "📁 My Terminal":
        files = user_data.get("files", [])
        if not files: 
            return bot.reply_to(m, "❌ No active source files found in your directory.")
        markup = types.InlineKeyboardMarkup()
        for f in files:
            markup.add(types.InlineKeyboardButton(text=f"📄 {f}", callback_data=f"file_{f}"))
        bot.send_message(uid, "📁 *Your Hosted Applications:*", reply_markup=markup, parse_mode="Markdown")

    elif text == "🆘 Support":
        help_text = (
            "🚀 *QUICK START GUIDE*\n\n"
            "1️⃣ Click on *'Upload Bot'* and send your single `.py` file or a packed `.zip` archive.\n"
            "2️⃣ If using a `.zip`, ensure your main script file is named `main.py` inside the root folder.\n"
            "3️⃣ Navigate to *'My Terminal'* to manually Boot, Restart, or Delete your microservices."
        )
        bot.reply_to(m, help_text, parse_mode="Markdown")

    elif text == "👑 Admin Panel" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔍 Audit & Control All Files", callback_data="admin_manage_all"))
        markup.row(types.InlineKeyboardButton("📢 System-Wide Broadcast", callback_data="admin_broadcast"))
        bot.send_message(uid, "👑 *Welcome to Executive Infrastructure Control Panel:*", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def file_handler(m):
    uid = m.from_user.id
    user_data = users.setdefault(uid, {"tier":"FREE","files":[]})
    
    filename = m.document.file_name
    if not filename.endswith((".py", ".zip")):
        return bot.reply_to(m, "❌ File Rejected. Only `.py` scripts or compressed `.zip` directories are permitted.")

    folder = user_folder(uid)
    save_path = os.path.join(folder, filename)
    msg = bot.reply_to(m, "📥 Syncing file with remote secure storage...")
    
    try:
        file_info = bot.get_file(m.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(save_path, 'wb') as f: 
            f.write(downloaded)
    except Exception as e:
        return bot.edit_message_text(f"❌ Storage Write Error: {e}", uid, msg.message_id)

    if filename not in user_data["files"]:
        user_data["files"].append(filename)
        save_data()

    if filename.endswith(".zip"):
        try:
            with zipfile.ZipFile(save_path, 'r') as z: 
                z.extractall(folder)
            install_requirements(folder, uid, msg.message_id)
            
            # Check if there is a main.py inside the extracted zip to auto-boot
            potential_main = os.path.join(folder, "main.py")
            if os.path.exists(potential_main):
                start_script_thread(uid, potential_main)
                bot.edit_message_text("✅ Archive decompressed. `main.py` detected and compiled successfully!", uid, msg.message_id)
            else:
                bot.edit_message_text("✅ Archive expanded. Go to 'My Terminal' and choose the file you wish to execute.", uid, msg.message_id)
        except Exception as zip_err:
            bot.edit_message_text(f"❌ Corrupt Archive: Extraction aborted. {zip_err}", uid, msg.message_id)
            
    elif filename.endswith(".py"):
        start_script_thread(uid, save_path)
        bot.edit_message_text(f"🚀 Live Deploy Active! `{filename}` is now executing seamlessly.", uid, msg.message_id)

# ================= HIGH-PERFORMANCE INTERACTIVE CALLBACKS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data

    # User Application Core Operations
    if data.startswith("file_"):
        fname = data[5:]
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("▶️ Boot Script", callback_data=f"run_{fname}"),
            types.InlineKeyboardButton("⏹ Terminate", callback_data=f"stop_{fname}")
        )
        markup.row(types.InlineKeyboardButton("🗑 Wipe File", callback_data=f"del_{fname}"))
        bot.edit_message_text(f"⚙️ *Process Manager:* `{fname}`\nSelect a system call command:", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("run_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path):
            start_script_thread(uid, path)
            bot.answer_callback_query(call.id, "▶️ Process spawned successfully.")
        else: 
            bot.answer_callback_query(call.id, "❌ Reference file target missing.")

    elif data.startswith("stop_"):
        fname = data[5:]
        path = os.path.join(user_folder(uid), fname)
        proc = active_scripts.get(uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[uid].pop(path, None)
            bot.answer_callback_query(call.id, "⏹ Execution terminated clean.")
        else: 
            bot.answer_callback_query(call.id, "❌ No active runtime found for this file.")

    elif data.startswith("del_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path): 
            os.remove(path)
        if fname in users.get(uid, {}).get("files", []):
            users[uid]["files"].remove(fname)
            save_data()
        bot.edit_message_text(f"✅ Securely purged `{fname}` from storage nodes.", uid, call.message.message_id, parse_mode="Markdown")

    # ================= EXECUTIVE SECURITY CONTROL (ADMIN ONLY) =================
    elif data == "admin_manage_all" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        has_files = False
        for uuid, udata in users.items():
            for f in udata.get("files", []):
                has_files = True
                markup.add(types.InlineKeyboardButton(text=f"👤 {uuid} | 📄 {f}", callback_data=f"admview_{uuid}_{f}"))
        if not has_files:
            return bot.edit_message_text("❌ No user files detected across all cluster containers.", uid, call.message.message_id)
        bot.edit_message_text("🔍 *Global Container File Audit:*", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admview_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📥 Download File", callback_data=f"admdown_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⏹ Admin Force Stop", callback_data=f"admstop_{target_uid}_{target_file}")
        )
        markup.row(
            types.InlineKeyboardButton("🗑 Admin Force Delete", callback_data=f"admdel_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⬅️ Back to Logs", callback_data="admin_manage_all")
        )
        bot.edit_message_text(f"📋 *Executive System Control*\n\n📄 *Target File:* `{target_file}`\n👤 *Client ID:* `{target_uid}`", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admdown_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        if os.path.exists(path):
            with open(path, "rb") as doc:
                bot.send_document(uid, doc, caption=f"⚙️ Audit Copy\nClient: `{target_uid}`\nFile: `{target_file}`", parse_mode="Markdown")
            bot.answer_callback_query(call.id, "✅ Transferred successfully.")
        else: 
            bot.answer_callback_query(call.id, "❌ Target data corrupted or missing.")

    elif data.startswith("admstop_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[target_uid].pop(path, None)
            bot.send_message(uid, f"✅ Executed administrative force stop on `{target_file}` belonging to ID {target_uid}.")
        else: 
            bot.answer_callback_query(call.id, f"❌ Process thread already idle.")

    elif data.startswith("admdel_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc: 
            proc.kill()
            active_scripts[target_uid].pop(path, None)
            
        if os.path.exists(path): 
            os.remove(path)
        if target_file in users.get(target_uid, {}).get("files", []):
            users[target_uid]["files"].remove(target_file)
            save_data()
        bot.edit_message_text(f"✅ Successfully deleted `{target_file}` from user storage block `{target_uid}`.", uid, call.message.message_id)

    elif data == "admin_broadcast" and uid == OWNER_ID:
        msg = bot.send_message(uid, "🗣 Send the message you wish to broadcast to all cluster nodes:")
        bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(m):
    if m.from_user.id == OWNER_ID:
        count = 0
        for user in list(users.keys()):
            try:
                bot.send_message(user, f"📢 *GLOBAL INFRASTRUCTURE NOTICE:*\n\n{m.text}", parse_mode="Markdown")
                count += 1
            except: 
                pass
        bot.send_message(OWNER_ID, f"✅ Broadcast delivered successfully to {count} connected cloud nodes.")

# ================= COLD-BOOT SYSTEM RESTORATION =================
def restore_all():
    load_data()
    print("🔄 Initializing system recovery: Restoring user processes...")
    for uid, data in users.items():
        folder = user_folder(uid)
        for f in data.get("files", []):
            # Auto restart individual main files on system cold boot
            if f == "main.py" or f.endswith(".py"):
                path = os.path.join(folder, f)
                if os.path.exists(path):
                    start_script_thread(uid, path)
    print("✅ System Recovery Complete. All services operational.")

if __name__ == "__main__":
    restore_all()
    print("🤖 Professional Hosting Engine Started Successfully on Render Web Service Server Core!")
    bot.infinity_polling()
