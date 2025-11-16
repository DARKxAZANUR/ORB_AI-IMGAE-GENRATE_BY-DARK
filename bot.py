#!/usr/bin/env python

import os
import random
import requests
import sqlite3
import threading
from urllib.parse import quote
import telebot
from telebot.types import (
    InputMediaPhoto, BotCommand, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    ChatMemberAdministrator
)
from io import BytesIO
import json
import time
from datetime import datetime
import re
import base64

# Initialize bot
def get_bot_token():
    try:
        with open('token.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise ValueError("token.txt file not found. Please create it with your Telegram bot token.")

TOKEN = get_bot_token()
bot = telebot.TeleBot(TOKEN)

# Admin user ID (replace with your Telegram ID)
ADMIN_ID = 1209735961  # Replace with your Telegram ID

# Your Telegram Channel ID (replace with your channel ID)
CHANNEL_ID = "@orbaidata"  # Replace with your channel ID

# SeeDream API Configuration - YAHAN APNA API KEY DALO
SEEDREAM_API_KEY = "743f4b84-6632-4b8b-8d89-3ea194f3d2eb"  # Tumhara actual SeeDream API key yahan dalo
SEEDREAM_API_URL = "https://api.seedream.ai/v1/images/generations"

# Database setup for users, groups and broadcast
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                last_name TEXT, date_joined TEXT, usage_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY, group_title TEXT, 
                group_username TEXT, date_added TEXT, is_active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS broadcast_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, message_text TEXT, 
                sent_date TEXT, sent_by INTEGER, success_count INTEGER, failed_count INTEGER, 
                group_success INTEGER, group_failed INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS image_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                prompt TEXT, width INTEGER, height INTEGER, model TEXT, 
                hd_enabled INTEGER, created_at TEXT, api_used TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Add user to database
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, date_joined) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, first_name, last_name, current_time))
    conn.commit()
    conn.close()

# Add group to database
def add_group(group_id, group_title, group_username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO groups (group_id, group_title, group_username, date_added) VALUES (?, ?, ?, ?)",
              (group_id, group_title, group_username, current_time))
    conn.commit()
    conn.close()

# Update user usage count
def update_usage(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET usage_count = usage_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# Save image request details
def save_image_request(user_id, prompt, width, height, model, is_hd, api_used):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO image_requests (user_id, prompt, width, height, model, hd_enabled, created_at, api_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (user_id, prompt, width, height, model, is_hd, current_time, api_used))
    conn.commit()
    conn.close()

# Get all users for broadcast
def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# Get all groups for broadcast
def get_all_groups():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT group_id FROM groups WHERE is_active = 1")
    groups = [row[0] for row in c.fetchall()]
    conn.close()
    return groups

# Get user stats
def get_user_stats():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(usage_count) FROM users")
    total_usage = c.fetchone()[0] or 0
    conn.close()
    return total_users, total_usage

# Save broadcast message with results
def save_broadcast_message(message_text, sent_by, success_count, failed_count, group_success, group_failed):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO broadcast_messages (message_text, sent_date, sent_by, success_count, failed_count, group_success, group_failed) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (message_text, current_time, sent_by, success_count, failed_count, group_success, group_failed))
    conn.commit()
    conn.close()

# Check if bot is admin in a group
def is_bot_admin(chat_id):
    try:
        member = bot.get_chat_member(chat_id, bot.get_me().id)
        return isinstance(member, ChatMemberAdministrator) and member.can_post_messages
    except:
        return False

# BROADCAST FUNCTION FOR BOTH USERS AND GROUPS
def broadcast_message(message_text, sent_by):
    # Send to users
    users = get_all_users()
    user_success = 0
    user_failed = 0
    
    for user_id in users:
        try:
            bot.send_message(user_id, message_text)
            user_success += 1
        except Exception as e:
            user_failed += 1
        time.sleep(0.1)
    
    # Send to groups where bot is admin
    groups = get_all_groups()
    group_success = 0
    group_failed = 0
    
    for group_id in groups:
        try:
            if is_bot_admin(group_id):
                bot.send_message(group_id, message_text)
                group_success += 1
            else:
                group_failed += 1
        except Exception as e:
            group_failed += 1
        time.sleep(0.2)
    
    # Save results
    save_broadcast_message(message_text, sent_by, user_success, user_failed, group_success, group_failed)
    
    return user_success, user_failed, group_success, group_failed

# AUTO-GROUP DETECTION - New group added handler
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            # Bot was added to a group
            group_id = message.chat.id
            group_title = message.chat.title
            group_username = message.chat.username
            add_group(group_id, group_title, group_username)
            
            # Send welcome message to group
            welcome_msg = "🤖 Thanks for adding me to this group! I'm an AI image generator bot. Use /help to see my commands."
            bot.send_message(group_id, welcome_msg)

# Set bot commands
bot.set_my_commands([
    BotCommand('start', 'Get started with the bot'),
    BotCommand('help', 'How to use the bot'),
    BotCommand('img', 'Generate AI images'),
    BotCommand('seedream', 'Generate image using SeeDream AI'),
    BotCommand('stats', 'Check your usage stats'),
    BotCommand('hd', 'Generate HD quality image'),
    BotCommand('name', 'Generate image with custom name/style'),
    BotCommand('gibliart', 'Generate Ghibli style art in 4K quality'),
    BotCommand('groups', 'List all groups where bot is added'),
    BotCommand('style', 'Apply artistic styles to images')
])

# Constants
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
DEFAULT_MODEL = "powered by Dark"
MAX_PROMPT_LENGTH = 400
ARTA_API_KEY = "AIzaSyB3-71wG0fIt0shj0ee4fvx1shcjJHGrrQ"

# Function to forward generated images to channel
def forward_to_channel(image_data, caption, user_info):
    try:
        if "GroupAnonymousBot" in user_info:
            user_info = "Anonymous User"
        
        full_caption = f"{caption}\n\n👤 Requested by: {user_info}\n📨 Shared via @OrbaiImageBot"
        bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_data,
            caption=full_caption,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Failed to forward image to channel: {e}")

# Function to forward any message to channel
def forward_message_to_channel(message):
    try:
        user_info = f"👤 User: @{message.from_user.username}" if message.from_user.username else f"👤 User: {message.from_user.first_name}"
        if message.text:
            text = f"{message.text}\n\n{user_info}"
            bot.send_message(chat_id=CHANNEL_ID, text=text)
        elif message.photo:
            caption = message.caption or ""
            full_caption = f"{caption}\n\n{user_info}"
            bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=full_caption)
    except Exception as e:
        print(f"❌ Failed to forward message to channel: {e}")

# Enhanced prompt processing
def enhance_prompt(prompt, style_name=None, is_hd=False):
    enhanced_prompt = prompt
    if style_name:
        enhanced_prompt = f"{prompt}, {style_name} style"
    if is_hd:
        enhanced_prompt += ", high quality, HD, 4K, 8K, detailed, sharp focus"
    return enhanced_prompt

# Ghibli style prompt enhancement
def enhance_ghibli_prompt(prompt):
    ghibli_keywords = "Studio Ghibli style, Miyazaki, anime, beautiful animation, whimsical, magical, soft colors, detailed backgrounds, masterpiece, 4K, ultra detailed"
    return f"{prompt}, {ghibli_keywords}"

# FIXED: SeeDream AI Image Generator - Simple & Working Version
def generate_seedream_image(prompt, width=1024, height=1024, style_preset=None):
    try:
        print(f"🔧 Attempting SeeDream API call with prompt: {prompt}")
        
        # Simple direct API call
        url = "https://api.seedream.ai/v1/images/generations"
        
        headers = {
            "Authorization": f"Bearer {SEEDREAM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "core",  # Ya fir tumhara specific model
            "prompt": prompt,
            "size": f"{width}x{height}",
            "num_images": 1
        }
        
        print(f"📤 Sending request to SeeDream API...")
        response = requests.post(url, headers=headers, json=data, timeout=60)
        print(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API Response: {result}")
            
            # Different response formats handle karte hain
            if 'data' in result and len(result['data']) > 0:
                image_url = result['data'][0].get('url')
            elif 'url' in result:
                image_url = result['url']
            else:
                print("❌ No image URL found in response")
                return None
                
            if image_url:
                print(f"📷 Downloading image from: {image_url}")
                image_response = requests.get(image_url, timeout=60)
                if image_response.status_code == 200:
                    return BytesIO(image_response.content)
        
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            
        return None
        
    except Exception as e:
        print(f"🔥 SeeDream API Error: {str(e)}")
        return None

# Pollinations.ai image generator - RELIABLE FALLBACK
def generate_pollinations_image(prompt, width, height, model, is_hd=False):
    try:
        base_url = "https://image.pollinations.ai/prompt/"
        encoded_prompt = quote(prompt)
        url = f"{base_url}{encoded_prompt}?width={width}&height={height}&nologo=true"
        
        if is_hd:
            url += "&enhance=true"
            
        print(f"🔄 Trying Pollinations: {url}")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            print("✅ Pollinations image generated successfully")
            return BytesIO(response.content)
        else:
            print(f"❌ Pollinations failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"🔥 Pollinations Error: {e}")
        return None

# Arta.ai image generator
def generate_arta_image(prompt, width, height, model, is_hd=False):
    try:
        print("🔄 Trying Arta AI...")
        auth_url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser"
        auth_params = {"key": ARTA_API_KEY}
        auth_headers = {
            "X-Android-Cert": "ADC09FCA89A2CE4D0D139031A2A587FA87EE4155",
            "X-Firebase-Gmpid": "1:713239656559:android:f9e37753e9ee7324cb759a",
            "X-Firebase-Client": "H4sIAAAAAAAA_6tWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 15; Build/12345)"
        }
        
        auth_response = requests.post(auth_url, params=auth_params, headers=auth_headers, timeout=30)
        if auth_response.status_code != 200:
            print("❌ Arta Auth failed")
            return None
            
        auth_data = auth_response.json()
        id_token = auth_data.get('idToken')
        if not id_token:
            print("❌ No ID token from Arta")
            return None
            
        generate_url = "https://firebasestorage.googleapis.com/v0/b/arta-ai.appspot.com/o/generate"
        generate_headers = {
            "Authorization": f"Bearer {id_token}",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 15; Build/12345)",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        generate_data = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "model": model,
            "negative_prompt": "",
            "num_inference_steps": 30 if is_hd else 20,
            "guidance_scale": 7.5,
            "seed": random.randint(0, 1000000)
        }
        
        generate_response = requests.post(generate_url, headers=generate_headers, json=generate_data, timeout=60)
        if generate_response.status_code != 200:
            print(f"❌ Arta generation failed: {generate_response.status_code}")
            return None
            
        result_data = generate_response.json()
        image_url = result_data.get('image_url')
        if not image_url:
            print("❌ No image URL from Arta")
            return None
            
        image_response = requests.get(image_url, timeout=30)
        if image_response.status_code == 200:
            print("✅ Arta image generated successfully")
            return BytesIO(image_response.content)
            
        return None
            
    except Exception as e:
        print(f"🔥 Arta AI Error: {e}")
        return None

# IMPROVED: Advanced image generation with better fallback
def generate_ai_image(prompt, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, is_hd=False, style=None, api_preference="auto"):
    print(f"🎯 Starting image generation for: {prompt}")
    
    # Try SeeDream first if specified
    if api_preference in ["auto", "seedream"] and SEEDREAM_API_KEY != "YOUR_SEEDREAM_API_KEY":
        print("🚀 Trying SeeDream AI...")
        seedream_image = generate_seedream_image(prompt, width, height, style)
        if seedream_image:
            print("✅ SeeDream AI Success!")
            return seedream_image, "SeeDream AI"
        else:
            print("❌ SeeDream AI Failed")
    
    # Try Pollinations as primary fallback (most reliable)
    print("🔄 Trying Pollinations AI...")
    pollinations_image = generate_pollinations_image(prompt, width, height, DEFAULT_MODEL, is_hd)
    if pollinations_image:
        print("✅ Pollinations AI Success!")
        return pollinations_image, "Pollinations AI"
    
    # Try Arta AI as last resort
    print("🔄 Trying Arta AI...")
    arta_image = generate_arta_image(prompt, width, height, DEFAULT_MODEL, is_hd)
    if arta_image:
        print("✅ Arta AI Success!")
        return arta_image, "Arta AI"
    
    print("❌ All APIs failed")
    return None, "Failed"

# Main keyboard
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('🖼 Generate Image'))
    keyboard.add(KeyboardButton('🌟 SeeDream AI'))
    keyboard.add(KeyboardButton('📊 My Stats'))
    keyboard.add(KeyboardButton('🎨 HD Quality'))
    keyboard.add(KeyboardButton('🎭 Artistic Styles'))
    keyboard.add(KeyboardButton('🇯🇵 Ghibli Art'))
    return keyboard

# Style selection keyboard
def style_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    styles = [
        ("Anime", "anime"),
        ("Realistic", "realistic"),
        ("Fantasy", "fantasy"),
        ("Cyberpunk", "cyberpunk"),
        ("Oil Painting", "oil-painting"),
        ("Watercolor", "watercolor"),
        ("3D Render", "3d-render"),
        ("Pixel Art", "pixel-art")
    ]
    buttons = [InlineKeyboardButton(text, callback_data=f"style_{data}") for text, data in styles]
    keyboard.add(*buttons)
    return keyboard

# NEW: Groups command to list all groups
@bot.message_handler(commands=['groups'])
def list_groups(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT group_id, group_title, group_username FROM groups WHERE is_active = 1")
    groups = c.fetchall()
    conn.close()
    
    if not groups:
        bot.reply_to(message, "❌ No groups found in database.")
        return
        
    groups_text = "📋 Groups where bot is added:\n\n"
    for group_id, group_title, group_username in groups:
        admin_status = "✅" if is_bot_admin(group_id) else "❌"
        groups_text += f"{admin_status} {group_title} (@{group_username if group_username else 'N/A'})\n"
    
    bot.reply_to(message, groups_text)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    add_user(message.from_user.id, message.from_user.username, 
             message.from_user.first_name, message.from_user.last_name)
    
    welcome_text = """
🤖 *Welcome to OrbAI Image Generator Bot!*

I can generate AI images from text prompts using multiple AI engines!

📝 *Basic Commands:*
/start - Show this welcome message  
/help - Show help information
/img [prompt] - Generate an image from text
/seedream [prompt] - Generate using SeeDream AI
/hd [prompt] - Generate HD quality image
/name [style] [prompt] - Generate with custom style
/gibliart [prompt] - Generate Ghibli style art in 4K quality
/style - Choose from artistic styles

🎨 *You can also use buttons:*
• 🖼 Generate Image - Create standard images
• 🌟 SeeDream AI - Use SeeDream AI engine
• 🎨 HD Quality - Create high-quality images
• 🎭 Artistic Styles - Apply artistic styles
• 🇯🇵 Ghibli Art - Create Studio Ghibli style artwork

*Examples:*
• `/img a beautiful sunset`
• `/seedream a futuristic city`
• `/hd a magical forest`

Enjoy creating! 🎨
    """
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=main_keyboard())
    
    try:
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    try:
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT usage_count FROM users WHERE user_id=?", (message.from_user.id,))
    result = c.fetchone()
    
    # Get API usage stats
    c.execute("SELECT api_used, COUNT(*) FROM image_requests GROUP BY api_used")
    api_stats = c.fetchall()
    
    conn.close()
    
    if result:
        usage_count = result[0]
        total_users, total_usage = get_user_stats()
        
        stats_text = f"""
📊 *Your Usage Stats:*
• Your image generations: {usage_count}
• Total users: {total_users}
• Total images generated: {total_usage}

🔧 *API Usage:*
"""
        for api_name, count in api_stats:
            stats_text += f"• {api_name}: {count}\n"
            
        bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "You haven't generated any images yet. Use /img to get started!")

# IMPROVED: SeeDream AI Command with better error handling
@bot.message_handler(commands=['seedream'])
def handle_seedream_request(message):
    try:
        add_user(message.from_user.id, message.from_user.username, 
                 message.from_user.first_name, message.from_user.last_name)
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    prompt = message.text.replace('/seedream', '').strip()
    if not prompt:
        bot.reply_to(message, "Please provide a prompt after /seedream. Example: /seedream a beautiful landscape")
        return
        
    if len(prompt) > MAX_PROMPT_LENGTH:
        bot.reply_to(message, f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.")
        return
        
    # Check if SeeDream API key is set
    if SEEDREAM_API_KEY == "YOUR_SEEDREAM_API_KEY":
        bot.reply_to(message, "❌ SeeDream API key not configured. Please contact admin.")
        return
        
    generating_msg = bot.reply_to(message, "🌟 Generating image with SeeDream AI... Please wait (15-30 seconds).")
    
    image_data, api_used = generate_ai_image(prompt, api_preference="seedream")
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, "SeeDream", False, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🌟 SeeDream AI Generated\nPrompt: {prompt}\nModel: SeeDream Core")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🌟 SeeDream AI Generated\nPrompt: {prompt}", user_info)
    else:
        error_msg = "❌ Failed to generate image with SeeDream AI. "
        error_msg += "Trying alternative APIs..."
        bot.edit_message_text(error_msg, message.chat.id, generating_msg.message_id)
        
        # Fallback to other APIs
        image_data, api_used = generate_ai_image(prompt, api_preference="auto")
        if image_data:
            update_usage(message.from_user.id)
            save_image_request(message.from_user.id, prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, "Fallback", False, api_used)
            
            bot.send_photo(message.chat.id, photo=image_data, 
                           caption=f"🖼 Image Generated (Fallback)\nPrompt: {prompt}\nAPI: {api_used}")
            
            bot.delete_message(message.chat.id, generating_msg.message_id)
            
            user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
            image_data.seek(0)
            forward_to_channel(image_data, f"🖼 Image Generated (Fallback)\nPrompt: {prompt}", user_info)
        else:
            bot.edit_message_text("❌ All image generation methods failed. Please try again later or use a different prompt.", 
                                 message.chat.id, generating_msg.message_id)

# NEW: Style command
@bot.message_handler(commands=['style'])
def handle_style_command(message):
    bot.reply_to(message, "🎨 Choose an artistic style for your image:", reply_markup=style_keyboard())

# Callback handler for styles
@bot.callback_query_handler(func=lambda call: call.data.startswith('style_'))
def handle_style_callback(call):
    style = call.data.replace('style_', '')
    bot.send_message(call.message.chat.id, f"🎨 You selected {style} style. Now send me your prompt for the image!")
    
    # Store the style preference for this user
    bot.register_next_step_handler(call.message, lambda msg: handle_styled_image(msg, style))

def handle_styled_image(message, style):
    prompt = message.text
    if not prompt:
        bot.reply_to(message, "Please provide a prompt for the image.")
        return
        
    generating_msg = bot.reply_to(message, f"🎨 Generating {style} style image... Please wait.")
    
    enhanced_prompt = f"{prompt}, {style} style"
    image_data, api_used = generate_ai_image(enhanced_prompt, api_preference="auto")
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, enhanced_prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, f"Style-{style}", False, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🎨 {style.title()} Style Image\nPrompt: {prompt}\nStyle: {style}")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🎨 {style.title()} Style Image\nPrompt: {prompt}", user_info)
    else:
        bot.edit_message_text(f"❌ Failed to generate {style} style image. Please try again.", 
                             message.chat.id, generating_msg.message_id)

# UPDATED BROADCAST COMMAND FOR GROUPS + USERS
@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
        
    if message.reply_to_message:
        if message.reply_to_message.text:
            broadcast_text = message.reply_to_message.text
        elif message.reply_to_message.caption:
            broadcast_text = message.reply_to_message.caption
        else:
            bot.reply_to(message, "❌ The replied message doesn't contain text.")
            return
    else:
        broadcast_text = message.text.replace('/broadcast', '').strip()
        if not broadcast_text:
            bot.reply_to(message, "❌ Please provide a message after /broadcast or reply to a message.")
            return
    
    sent_msg = bot.reply_to(message, "📤 Sending broadcast to all users and groups...")
    
    user_success, user_failed, group_success, group_failed = broadcast_message(broadcast_text, message.from_user.id)
    
    result_text = f"""
✅ Broadcast Completed!

👥 Users:
• ✅ Success: {user_success}
• ❌ Failed: {user_failed}

📋 Groups:
• ✅ Success: {group_success}
• ❌ Failed: {group_failed}

📊 Total Reach: {user_success + group_success} people/groups
"""
    bot.edit_message_text(result_text, message.chat.id, sent_msg.message_id)

# Handle HD image generation
@bot.message_handler(commands=['hd'])
def handle_hd_request(message):
    try:
        add_user(message.from_user.id, message.from_user.username, 
                 message.from_user.first_name, message.from_user.last_name)
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    prompt = message.text.replace('/hd', '').strip()
    if not prompt:
        bot.reply_to(message, "Please provide a prompt after /hd. Example: /hd a beautiful landscape")
        return
        
    if len(prompt) > MAX_PROMPT_LENGTH:
        bot.reply_to(message, f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.")
        return
        
    generating_msg = bot.reply_to(message, "🖼 Generating HD image... Please wait.")
    enhanced_prompt = enhance_prompt(prompt, is_hd=True)
    
    image_data, api_used = generate_ai_image(enhanced_prompt, is_hd=True)
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, enhanced_prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_MODEL, True, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🖼 HD Image Generated\nPrompt: {prompt}\nAPI: {api_used}")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🖼 HD Image Generated\nPrompt: {prompt}", user_info)
    else:
        bot.edit_message_text("❌ Failed to generate HD image. Please try again with a different prompt.", 
                             message.chat.id, generating_msg.message_id)

# IMPROVED: Main image generation with better error handling
@bot.message_handler(commands=['img'])
def handle_image_request(message):
    try:
        add_user(message.from_user.id, message.from_user.username, 
                 message.from_user.first_name, message.from_user.last_name)
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    prompt = message.text.replace('/img', '').strip()
    if not prompt:
        bot.reply_to(message, "Please provide a prompt after /img. Example: /img a cute cat")
        return
        
    if len(prompt) > MAX_PROMPT_LENGTH:
        bot.reply_to(message, f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.")
        return
        
    generating_msg = bot.reply_to(message, "🖼 Generating image... Please wait (10-20 seconds).")
    
    image_data, api_used = generate_ai_image(prompt)
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_MODEL, False, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🖼 Image Generated\nPrompt: {prompt}\nAPI: {api_used}")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🖼 Image Generated\nPrompt: {prompt}", user_info)
    else:
        bot.edit_message_text("❌ Failed to generate image. Please try again with a different prompt or check if APIs are working.", 
                             message.chat.id, generating_msg.message_id)

# Handle custom name/style
@bot.message_handler(commands=['name'])
def handle_name_request(message):
    try:
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    text = message.text.replace('/name', '').strip()
    parts = text.split(' ', 1)
    
    if len(parts) < 2:
        bot.reply_to(message, "Please provide style and prompt. Example: /name anime a beautiful girl")
        return
        
    style_name, prompt = parts[0], parts[1]
    
    if len(prompt) > MAX_PROMPT_LENGTH:
        bot.reply_to(message, f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.")
        return
        
    generating_msg = bot.reply_to(message, f"🎨 Generating {style_name} style image... Please wait.")
    enhanced_prompt = enhance_prompt(prompt, style_name)
    
    image_data, api_used = generate_ai_image(enhanced_prompt)
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, enhanced_prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, f"Custom-{style_name}", False, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🎨 {style_name.title()} Style Image\nPrompt: {prompt}\nAPI: {api_used}")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🎨 {style_name.title()} Style Image\nPrompt: {prompt}", user_info)
    else:
        bot.edit_message_text("❌ Failed to generate image. Please try again with a different prompt.", 
                             message.chat.id, generating_msg.message_id)

# Handle Ghibli art
@bot.message_handler(commands=['gibliart'])
def handle_ghibli_request(message):
    try:
        forward_message_to_channel(message)
    except Exception as e:
        print(f"Forwarding failed: {e}")
    
    prompt = message.text.replace('/gibliart', '').strip()
    if not prompt:
        bot.reply_to(message, "Please provide a prompt after /gibliart. Example: /gibliart a magical forest")
        return
        
    if len(prompt) > MAX_PROMPT_LENGTH:
        bot.reply_to(message, f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.")
        return
        
    generating_msg = bot.reply_to(message, "🇯🇵 Generating Ghibli style art... Please wait.")
    enhanced_prompt = enhance_ghibli_prompt(prompt)
    
    image_data, api_used = generate_ai_image(enhanced_prompt, is_hd=True)
    
    if image_data:
        update_usage(message.from_user.id)
        save_image_request(message.from_user.id, enhanced_prompt, DEFAULT_WIDTH, DEFAULT_HEIGHT, "Ghibli", True, api_used)
        
        bot.send_photo(message.chat.id, photo=image_data, 
                       caption=f"🇯🇵 Ghibli Style Art\nPrompt: {prompt}\nAPI: {api_used}")
        
        bot.delete_message(message.chat.id, generating_msg.message_id)
        
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        image_data.seek(0)
        forward_to_channel(image_data, f"🇯🇵 Ghibli Style Art\nPrompt: {prompt}", user_info)
    else:
        bot.edit_message_text("❌ Failed to generate Ghibli art. Please try again with a different prompt.", 
                             message.chat.id, generating_msg.message_id)

# Handle button messages
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        add_user(message.from_user.id, message.from_user.username, 
                 message.from_user.first_name, message.from_user.last_name)
    except:
        pass
        
    if message.text == '🖼 Generate Image':
        bot.reply_to(message, "Please send your image prompt. You can also use /img command.")
        
    elif message.text == '🌟 SeeDream AI':
        bot.reply_to(message, "Please send your prompt for SeeDream AI generation. You can also use /seedream command.")
        
    elif message.text == '📊 My Stats':
        show_stats(message)
        
    elif message.text == '🎨 HD Quality':
        bot.reply_to(message, "Please send your prompt for HD quality image. You can also use /hd command.")
        
    elif message.text == '🎭 Artistic Styles':
        handle_style_command(message)
        
    elif message.text == '🇯🇵 Ghibli Art':
        bot.reply_to(message, "Please send your prompt for Ghibli style art. You can also use /gibliart command.")
        
    else:
        # If it's not a button, treat as prompt for image generation
        if len(message.text) > 5 and len(message.text) <= MAX_PROMPT_LENGTH:
            generating_msg = bot.reply_to(message, "🖼 Generating image... Please wait.")
            
            image_data, api_used = generate_ai_image(message.text)
            
            if image_data:
                update_usage(message.from_user.id)
                save_image_request(message.from_user.id, message.text, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_MODEL, False, api_used)
                
                bot.send_photo(message.chat.id, photo=image_data, 
                               caption=f"🖼 Image Generated\nPrompt: {message.text}\nAPI: {api_used}")
                
                bot.delete_message(message.chat.id, generating_msg.message_id)
                
                user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
                image_data.seek(0)
                forward_to_channel(image_data, f"🖼 Image Generated\nPrompt: {message.text}", user_info)
            else:
                bot.edit_message_text("❌ Failed to generate image. Please try again with a different prompt.", 
                                     message.chat.id, generating_msg.message_id)

if __name__ == "__main__":
    print("🤖 OrbAI Image Generator Bot is running...")
    print(f"🔑 SeeDream API Key: {'✅ Set' if SEEDREAM_API_KEY != 'YOUR_SEEDREAM_API_KEY' else '❌ Not Set'}")
    bot.infinity_polling()