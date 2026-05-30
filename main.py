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
from flask import Flask  # Render ዌብ ሰርቪስ እንዳይዘጋ የተጨመረ

# ================= FLASK SERVER FOR RENDER =================
app = Flask('')

@app.route('/')
def home():
    return "Xerox Hosting Bot is Running 24/7!"

def run_flask():
    # Render የሚሰጠውን PORT በራስ-ሰር ያነባል፣ ከሌለ 8080 ይጠቀማል
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ዌብ ሰርቨሩን በጀርባ (Thread) ማስነሳት
threading.Thread(target=run_flask, daemon=True).start()

# ================= BOT CONFIG =================
BOT_TOKEN = "8896468531:AAGG-6Psr35XmWT33cu3Yev7y5hKDc_6drw"
OWNER_ID = 8700421304       

STORAGE_DIR = "user_files"
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
DATA_FILE = os.path.join(STORAGE_DIR, "users.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f: json.dump({}, f)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ================= GLOBALS =================
users = {}
active_scripts = {}      
logs_store = {}          
START_TIME = datetime.now()

# ================= DATA PERSISTENCE =================
def save_data():
    try:
        with open(DATA_FILE, "w") as f: json.dump(users, f, indent=4)
    except Exception as e: print(f"Save Error: {e}")

def load_data():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                raw_data = json.load(f)
                users.clear()
                for k, v in raw_data.items(): users[int(k)] = v
        except: users = {}

def user_folder(uid):
    path = os.path.join(UPLOAD_DIR, str(uid))
    os.makedirs(path, exist_ok=True)
    return path

# ================= CLEAN BUTTONS =================
def control_buttons(uid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🌏 Upload"), types.KeyboardButton("📁 My Files"))
    markup.row(types.KeyboardButton("📊 Live Logs"), types.KeyboardButton("⏹ Stop My Bots"))
    markup.row(types.KeyboardButton("🚀 Status"), types.KeyboardButton("🆘 Help"))
    if uid == OWNER_ID:
        markup.row(types.KeyboardButton("👑 Admin Panel"))
    return markup

# ================= UNIVERSAL RUNNER =================
def run_script_sync(user_id, file_path):
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(file_path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    active_scripts.setdefault(user_id, {})[file_path] = proc
    logs_store.setdefault(user_id, {})[file_path] = []

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
        if line:
            text = line.strip()
            logs_store[user_id][file_path].append(text)
            logs_store[user_id][file_path] = logs_store[user_id][file_path][-50:]
    
    if user_id in active_scripts and file_path in active_scripts[user_id]:
        active_scripts[user_id].pop(file_path, None)

def start_script_thread(user_id, file_path):
    t = threading.Thread(target=run_script_sync, args=(user_id, file_path), daemon=True)
    t.start()

def install_requirements(folder):
    req_file = os.path.join(folder, "requirements.txt")
    if os.path.exists(req_file):
        try: subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        except: pass

# ================= COMMAND HANDLERS =================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    users.setdefault(uid, {"tier": "FREE", "files": []})
    if uid == OWNER_ID: users[uid]["tier"] = "OWNER"
    save_data()

    welcome_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃    🚀 XEROX HOSTING BOT   ┃\n"
        "┃     WEB SERVICE VERSION   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👤 Welcome, {m.from_user.first_name}!\n"
        f"🆔 Your ID: {uid}\n"
        f"🎫 Tier: {users[uid]['tier']}\n\n"
        "የፈለጉትን ተግባር ከታች ባሉት በተኖች ይምረጡ።"
    )
    bot.send_message(uid, welcome_text, reply_markup=control_buttons(uid))

@bot.message_handler(func=lambda m: True, content_types=['text'])
def keyboard_handler(m):
    uid = m.from_user.id
    text = m.text
    user_data = users.setdefault(uid, {"tier": "FREE", "files": []})

    if text == "🌏 Upload":
        bot.reply_to(m, "📤 እባክህ የ `.py` ወይም የ `.zip` ፋይልህን ላክ።")
    
    elif text == "📁 My Files":
        files = user_data.get("files", [])
        if not files: return bot.reply_to(m, "❌ ምንም የተሰቀለ ፋይል የለም።")
        markup = types.InlineKeyboardMarkup()
        for f in files:
            markup.add(types.InlineKeyboardButton(text=f, callback_data=f"file_{f}"))
        bot.send_message(uid, "📁 የሰቀልካቸው ፋይሎች ዝርዝር፦", reply_markup=markup)

    elif text == "📊 Live Logs":
        user_logs = logs_store.get(uid, {})
        if not user_logs: return bot.reply_to(m, "❌ በአሁኑ ሰዓት እየሰራ ያለ ቦት የለም።")
        for file_path, lines in user_logs.items():
            last_lines = "\n".join(lines[-15:])
            bot.send_message(uid, f"📜 Logs for {os.path.basename(file_path)}:\n```\n{last_lines}\n```", parse_mode="Markdown")

    elif text == "⏹ Stop My Bots":
        if uid in active_scripts:
            for p in list(active_scripts[uid].values()): p.kill()
            active_scripts[uid] = {}
        bot.reply_to(m, "⏹ ሁሉንም ቦቶችህን አቁመሃል።")

    elif text == "🚀 Status":
        total_users = len(users)
        running_scripts = sum(len(active_scripts.get(uuid, {})) for uuid in active_scripts)
        uptime = str(datetime.now() - START_TIME).split('.')[0]
        bot.send_message(uid, f"📊 SYSTEM STATUS\n\n👥 Total Users: {total_users}\n🟢 Active Running Scripts: {running_scripts}\n⏱️ Uptime: {uptime}")

    elif text == "🆘 Help":
        bot.reply_to(m, "🚀 **እንዴት መጠቀም ይቻላል?**\n1. ፋይል ለመጫን 'Upload' ተጫን\n2. የጫንከውን ፋይል ለማዘዝ 'My Files' ውስጥ ግባ\n3. የቦትህን ሂደት ለማየት 'Live Logs' ተጠቀም።")

    elif text == "👑 Admin Panel" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔍 የሁሉንም ሰው ፋይል እይ / አስተዳድር", callback_data="admin_manage_all"))
        markup.row(types.InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_broadcast"))
        bot.send_message(uid, "👑 እንኳን ወደ አስተዳዳሪ ፓናል በሰላም መጡ። የሚፈልጉትን ቁጥጥር ይምረጡ፡", reply_markup=markup)

@bot.message_handler(content_types=['document'])
def file_handler(m):
    uid = m.from_user.id
    user_data = users.setdefault(uid, {"tier":"FREE","files":[]})
    
    filename = m.document.file_name
    if not filename.endswith((".py", ".zip")):
        return bot.reply_to(m, "❌ የ `.py` ወይም `.zip` ፋይል ብቻ ነው የሚፈቀደው።")

    folder = user_folder(uid)
    save_path = os.path.join(folder, filename)
    msg = bot.reply_to(m, "📥 ፋይሉ እየወረደ ነው...")
    
    try:
        file_info = bot.get_file(m.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(save_path, 'wb') as f: f.write(downloaded)
    except Exception as e:
        return bot.edit_message_text(f"❌ ስህተት አጋጥሟል: {e}", uid, msg.message_id)

    if filename not in user_data["files"]:
        user_data["files"].append(filename)
        save_data()

    if filename.endswith(".zip"):
        with zipfile.ZipFile(save_path, 'r') as z: z.extractall(folder)
        install_requirements(folder)
        bot.edit_message_text("✅ ZIP ፋይሉ ተዘርግቷል። 'My Files' ውስጥ ገብተው ማዘዝ ይችላሉ።", uid, msg.message_id)
    elif filename.endswith(".py"):
        start_script_thread(uid, save_path)
        bot.edit_message_text(f"🚀 {filename} በተሳካ ሁኔታ ተነስቷል!", uid, msg.message_id)

# ================= CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data

    if data.startswith("file_"):
        fname = data[5:]
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("▶️ Start", callback_data=f"run_{fname}"),
            types.InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{fname}")
        )
        markup.row(types.InlineKeyboardButton("🗑 ሰርዝ", callback_data=f"del_{fname}"))
        bot.edit_message_text(f"⚙️ **ፋይል:** `{fname}`\nየሚፈልጉትን እርምጃ ይምረጡ፡", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("run_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path):
            start_script_thread(uid, path)
            bot.answer_callback_query(call.id, "▶️ ቦቱ ተነስቷል")
        else: bot.answer_callback_query(call.id, "❌ ፋይሉ አልተገኘም")

    elif data.startswith("stop_"):
        fname = data[5:]
        path = os.path.join(user_folder(uid), fname)
        proc = active_scripts.get(uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[uid].pop(path, None)
            bot.answer_callback_query(call.id, "⏹ ቦቱ ቆሟል")
        else: bot.answer_callback_query(call.id, "❌ ቦቱ አልነበረም")

    elif data.startswith("del_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path): os.remove(path)
        if fname in users.get(uid, {}).get("files", []):
            users[uid]["files"].remove(fname)
            save_data()
        bot.edit_message_text(f"✅ {fname} በተሳካ ሁኔታ ተሰርዟል።", uid, call.message.message_id)

    elif data == "admin_manage_all" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        has_files = False
        for uuid, udata in users.items():
            for f in udata.get("files", []):
                has_files = True
                markup.add(types.InlineKeyboardButton(text=f"👤 {uuid} | 📄 {f}", callback_data=f"admview_{uuid}_{f}"))
        if not has_files:
            return bot.edit_message_text("❌ በሲስተሙ ላይ ምንም የተጫነ ፋይል የለም።", uid, call.message.message_id)
        bot.edit_message_text("🔍 የሁሉም ተጠቃሚዎች ፋይሎች፤ ለመቆጣጠር አንዱን ይጫኑ፡", uid, call.message.message_id, reply_markup=markup)

    elif data.startswith("admview_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📥 አውርድ (Download)", callback_data=f"admdown_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⏹ አስቁም (Stop)", callback_data=f"admstop_{target_uid}_{target_file}")
        )
        markup.row(
            types.InlineKeyboardButton("🗑 ሰርዝ (Delete)", callback_data=f"admdel_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⬅️ ወደኋላ", callback_data="admin_manage_all")
        )
        bot.edit_message_text(f"📋 **የአስተዳዳሪ መቆጣጠሪያ**\n\n📄 **ፋይል:** `{target_file}`\n👤 **የባለቤቱ ID:** `{target_uid}`", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admdown_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        if os.path.exists(path):
            with open(path, "rb") as doc:
                bot.send_document(uid, doc, caption=f"📄 User ID: `{target_uid}`\nFile: `{target_file}`")
            bot.answer_callback_query(call.id, "✅ ፋይሉ ተልኳል")
        else: bot.answer_callback_query(call.id, "❌ ፋይሉ አልተገኘም")

    elif data.startswith("admstop_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[target_uid].pop(path, None)
            bot.send_message(uid, f"✅ የቦት ፋይል `{target_file}` (ID: {target_uid}) ቆሟል።")
        else: bot.answer_callback_query(call.id, "❌ ይህ ቦት በአሁኑ ሰዓት እየሰራ አይደለም")

    elif data.startswith("admdel_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc: 
            proc.kill()
            active_scripts[target_uid].pop(path, None)
        if os.path.exists(path): os.remove(path)
        if target_file in users.get(target_uid, {}).get("files", []):
            users[target_uid]["files"].remove(target_file)
            save_data()
        bot.edit_message_text(f"✅ የባለቤት ID `{target_uid}` የሆነው `{target_file}` ፋይል ሙሉ በሙሉ ተሰርዟል።", uid, call.message.message_id)

    elif data == "admin_broadcast" and uid == OWNER_ID:
        msg = bot.send_message(uid, "🗣 ለሁሉም ተጠቃሚዎች የሚተላለፈውን መልዕክት ይጻፉ፡")
        bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(m):
    if m.from_user.id == OWNER_ID:
        count = 0
        for user in list(users.keys()):
            try:
                bot.send_message(user, f"📢 **የአስተዳዳሪ መልዕክት፡**\n\n{m.text}")
                count += 1
            except: pass
        bot.send_message(OWNER_ID, f"✅ መልዕክቱ ለ {count} ተጠቃሚዎች ተልኳል።")

# ================= STARTUP LOGIC =================
def restore_all():
    load_data()
    print("🔄 Restoring scripts...")
    for uid, data in users.items():
        folder = user_folder(uid)
        for f in data.get("files", []):
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                if os.path.exists(path):
                    start_script_thread(uid, path)
    print("✅ System Ready")

if __name__ == "__main__":
    restore_all()
    print("🤖 Bot Started on Render as Web Service!")
    bot.infinity_polling()
        if line:
            text = line.strip()
            logs_store[user_id][file_path].append(text)
            logs_store[user_id][file_path] = logs_store[user_id][file_path][-50:]
    
    if user_id in active_scripts and file_path in active_scripts[user_id]:
        active_scripts[user_id].pop(file_path, None)

def start_script_thread(user_id, file_path):
    t = threading.Thread(target=run_script_sync, args=(user_id, file_path), daemon=True)
    t.start()

def install_requirements(folder):
    req_file = os.path.join(folder, "requirements.txt")
    if os.path.exists(req_file):
        try: subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        except: pass

# ================= COMMAND HANDLERS =================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    users.setdefault(uid, {"tier": "FREE", "files": []})
    if uid == OWNER_ID: users[uid]["tier"] = "OWNER"
    save_data()

    welcome_text = (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃    🚀 XEROX HOSTING BOT   ┃\n"
        "┃     NO API-HASH VERSION   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👤 Welcome, {m.from_user.first_name}!\n"
        f"🆔 Your ID: {uid}\n"
        f"🎫 Tier: {users[uid]['tier']}\n\n"
        "የፈለጉትን ተግባር ከታች ባሉት በተኖች ይምረጡ።"
    )
    bot.send_message(uid, welcome_text, reply_markup=control_buttons(uid))

@bot.message_handler(func=lambda m: True, content_types=['text'])
def keyboard_handler(m):
    uid = m.from_user.id
    text = m.text
    user_data = users.setdefault(uid, {"tier": "FREE", "files": []})

    if text == "🌏 Upload":
        bot.reply_to(m, "📤 እባክህ የ `.py` ወይም የ `.zip` ፋይልህን ላክ።")
    
    elif text == "📁 My Files":
        files = user_data.get("files", [])
        if not files: return bot.reply_to(m, "❌ ምንም የተሰቀለ ፋይል የለም።")
        markup = types.InlineKeyboardMarkup()
        for f in files:
            markup.add(types.InlineKeyboardButton(text=f, callback_data=f"file_{f}"))
        bot.send_message(uid, "📁 የሰቀልካቸው ፋይሎች ዝርዝር፦", reply_markup=markup)

    elif text == "📊 Live Logs":
        user_logs = logs_store.get(uid, {})
        if not user_logs: return bot.reply_to(m, "❌ በአሁኑ ሰዓት እየሰራ ያለ ቦት የለም።")
        for file_path, lines in user_logs.items():
            last_lines = "\n".join(lines[-15:])
            bot.send_message(uid, f"📜 Logs for {os.path.basename(file_path)}:\n```\n{last_lines}\n```", parse_mode="Markdown")

    elif text == "⏹ Stop My Bots":
        if uid in active_scripts:
            for p in list(active_scripts[uid].values()): p.kill()
            active_scripts[uid] = {}
        bot.reply_to(m, "⏹ ሁሉንም ቦቶችህን አቁመሃል።")

    elif text == "🚀 Status":
        total_users = len(users)
        running_scripts = sum(len(active_scripts.get(uuid, {})) for uuid in active_scripts)
        uptime = str(datetime.now() - START_TIME).split('.')[0]
        bot.send_message(uid, f"📊 SYSTEM STATUS\n\n👥 Total Users: {total_users}\n🟢 Active Running Scripts: {running_scripts}\n⏱️ Uptime: {uptime}")

    elif text == "🆘 Help":
        bot.reply_to(m, "🚀 **እንዴት መጠቀም ይቻላል?**\n1. ፋይል ለመጫን 'Upload' ተጫን\n2. የጫንከውን ፋይል ለማዘዝ 'My Files' ውስጥ ግባ\n3. የቦትህን ሂደት ለማየት 'Live Logs' ተጠቀም።")

    elif text == "👑 Admin Panel" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔍 የሁሉንም ሰው ፋይል እይ / አስተዳድር", callback_data="admin_manage_all"))
        markup.row(types.InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_broadcast"))
        bot.send_message(uid, "👑 እንኳን ወደ አስተዳዳሪ ፓናል በሰላም መጡ። የሚፈልጉትን ቁጥጥር ይምረጡ፡", reply_markup=markup)

@bot.message_handler(content_types=['document'])
def file_handler(m):
    uid = m.from_user.id
    user_data = users.setdefault(uid, {"tier":"FREE","files":[]})
    
    filename = m.document.file_name
    if not filename.endswith((".py", ".zip")):
        return bot.reply_to(m, "❌ የ `.py` ወይም `.zip` ፋይል ብቻ ነው የሚፈቀደው።")

    folder = user_folder(uid)
    save_path = os.path.join(folder, filename)
    msg = bot.reply_to(m, "📥 ፋይሉ እየወረደ ነው...")
    
    try:
        file_info = bot.get_file(m.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(save_path, 'wb') as f: f.write(downloaded)
    except Exception as e:
        return bot.edit_message_text(f"❌ ስህተት አጋጥሟል: {e}", uid, msg.message_id)

    if filename not in user_data["files"]:
        user_data["files"].append(filename)
        save_data()

    if filename.endswith(".zip"):
        with zipfile.ZipFile(save_path, 'r') as z: z.extractall(folder)
        install_requirements(folder)
        bot.edit_message_text("✅ ZIP ፋይሉ ተዘርግቷል። 'My Files' ውስጥ ገብተው ማዘዝ ይችላሉ።", uid, msg.message_id)
    elif filename.endswith(".py"):
        start_script_thread(uid, save_path)
        bot.edit_message_text(f"🚀 {filename} በተሳካ ሁኔታ ተነስቷል!", uid, msg.message_id)

# ================= CALLBACK HANDLER (የላቀ የአስተዳዳሪ ቁጥጥር) =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data

    # የተጠቃሚ ፋይል መቆጣጠሪያ
    if data.startswith("file_"):
        fname = data[5:]
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("▶️ Start", callback_data=f"run_{fname}"),
            types.InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{fname}")
        )
        markup.row(types.InlineKeyboardButton("🗑 ሰርዝ", callback_data=f"del_{fname}"))
        bot.edit_message_text(f"⚙️ **ፋይል:** `{fname}`\nየሚፈልጉትን እርምጃ ይምረጡ፡", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("run_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path):
            start_script_thread(uid, path)
            bot.answer_callback_query(call.id, "▶️ ቦቱ ተነስቷል")
        else: bot.answer_callback_query(call.id, "❌ ፋይሉ አልተገኘም")

    elif data.startswith("stop_"):
        fname = data[5:]
        path = os.path.join(user_folder(uid), fname)
        proc = active_scripts.get(uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[uid].pop(path, None)
            bot.answer_callback_query(call.id, "⏹ ቦቱ ቆሟል")
        else: bot.answer_callback_query(call.id, "❌ ቦቱ አልነበረም")

    elif data.startswith("del_"):
        fname = data[4:]
        path = os.path.join(user_folder(uid), fname)
        if os.path.exists(path): os.remove(path)
        if fname in users.get(uid, {}).get("files", []):
            users[uid]["files"].remove(fname)
            save_data()
        bot.edit_message_text(f"✅ {fname} በተሳካ ሁኔታ ተሰርዟል።", uid, call.message.message_id)

    # =============== አድሚን ብቻ (ADMIN PANEL) ===============
    elif data == "admin_manage_all" and uid == OWNER_ID:
        markup = types.InlineKeyboardMarkup()
        has_files = False
        for uuid, udata in users.items():
            for f in udata.get("files", []):
                has_files = True
                markup.add(types.InlineKeyboardButton(text=f"👤 {uuid} | 📄 {f}", callback_data=f"admview_{uuid}_{f}"))
        if not has_files:
            return bot.edit_message_text("❌ በሲስተሙ ላይ ምንም የተጫነ ፋይል የለም።", uid, call.message.message_id)
        bot.edit_message_text("🔍 የሁሉም ተጠቃሚዎች ፋይሎች፤ ለመቆጣጠር አንዱን ይጫኑ፡", uid, call.message.message_id, reply_markup=markup)

    elif data.startswith("admview_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📥 አውርድ (Download)", callback_data=f"admdown_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⏹ አስቁም (Stop)", callback_data=f"admstop_{target_uid}_{target_file}")
        )
        markup.row(
            types.InlineKeyboardButton("🗑 ሰርዝ (Delete)", callback_data=f"admdel_{target_uid}_{target_file}"),
            types.InlineKeyboardButton("⬅️ ወደኋላ", callback_data="admin_manage_all")
        )
        bot.edit_message_text(f"📋 **የአስተዳዳሪ መቆጣጠሪያ**\n\n📄 **ፋይል:** `{target_file}`\n👤 **የባለቤቱ ID:** `{target_uid}`", uid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admdown_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        
        if os.path.exists(path):
            with open(path, "rb") as doc:
                bot.send_document(uid, doc, caption=f"📄 User ID: `{target_uid}`\nFile: `{target_file}`")
            bot.answer_callback_query(call.id, "✅ ፋይሉ ተልኳል")
        else: bot.answer_callback_query(call.id, "❌ ፋይሉ አልተገኘም")

    elif data.startswith("admstop_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc:
            proc.kill()
            active_scripts[target_uid].pop(path, None)
            bot.send_message(uid, f"✅ የቦት ፋይል `{target_file}` (ID: {target_uid}) ቆሟል።")
        else: bot.answer_callback_query(call.id, "❌ ይህ ቦት በአሁኑ ሰዓት እየሰራ አይደለም")

    elif data.startswith("admdel_") and uid == OWNER_ID:
        parts = data.split("_")
        target_uid = int(parts[1])
        target_file = parts[2]
        path = os.path.join(user_folder(target_uid), target_file)
        
        proc = active_scripts.get(target_uid, {}).get(path)
        if proc: 
            proc.kill()
            active_scripts[target_uid].pop(path, None)
            
        if os.path.exists(path): os.remove(path)
        if target_file in users.get(target_uid, {}).get("files", []):
            users[target_uid]["files"].remove(target_file)
            save_data()
            
        bot.edit_message_text(f"✅ የባለቤት ID `{target_uid}` የሆነው `{target_file}` ፋይል ሙሉ በሙሉ ተሰርዟል።", uid, call.message.message_id)

    elif data == "admin_broadcast" and uid == OWNER_ID:
        msg = bot.send_message(uid, "🗣 ለሁሉም ተጠቃሚዎች የሚተላለፈውን መልዕክት ይጻፉ፡")
        bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(m):
    if m.from_user.id == OWNER_ID:
        count = 0
        for user in list(users.keys()):
            try:
                bot.send_message(user, f"📢 **የአስተዳዳሪ መልዕክት፡**\n\n{m.text}")
                count += 1
            except: pass
        bot.send_message(OWNER_ID, f"✅ መልዕክቱ ለ {count} ተጠቃሚዎች ተልኳል።")

# ================= STARTUP LOGIC =================
def restore_all():
    load_data()
    print("🔄 Restoring scripts...")
    for uid, data in users.items():
        folder = user_folder(uid)
        for f in data.get("files", []):
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                if os.path.exists(path):
                    start_script_thread(uid, path)
    print("✅ System Ready")

if __name__ == "__main__":
    restore_all()
    print("🤖 Bot Started on Render without API-HASH!")
    bot.infinity_polling()
