import os
import json
from datetime import datetime, timedelta
from collections import deque

CHATS_MEMORY_DIR = "chatsmemory"
MAX_MESSAGES = 60  # 30 pairs (user + AI)
MESSAGE_RETENTION_DAYS = 30

def ensure_memory_dir():
    """Ensure the chatsmemory directory exists"""
    if not os.path.exists(CHATS_MEMORY_DIR):
        os.makedirs(CHATS_MEMORY_DIR)

def get_user_file_path(user_id, platform):
    """Get the file path for a user's chat memory"""
    return os.path.join(CHATS_MEMORY_DIR, f"{platform}_{user_id}_chats.json")

def update_user_memory(user_id, platform, message, sender="user"):
    """Update user's chat memory with a new message"""
    ensure_memory_dir()
    file_path = get_user_file_path(user_id, platform)
    
    try:
        # Load existing messages
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                messages = deque(data['messages'], maxlen=MAX_MESSAGES)
                last_cleaned = datetime.fromisoformat(data['last_cleaned'])
        else:
            messages = deque(maxlen=MAX_MESSAGES)
            last_cleaned = datetime.now()
        
        # Add new message with timestamp and sender
        prefix = "User:" if sender == "user" else "AI:"
        messages.append({
            "text": f"{prefix} {message}",
            "timestamp": datetime.now().isoformat(),
            "sender": sender
        })
        
        # Clean old messages if it's been a while
        if datetime.now() - last_cleaned > timedelta(days=1):
            cutoff = datetime.now() - timedelta(days=MESSAGE_RETENTION_DAYS)
            messages = deque(
                [msg for msg in messages if datetime.fromisoformat(msg['timestamp']) > cutoff],
                maxlen=MAX_MESSAGES
            )
            last_cleaned = datetime.now()
        
        # Save to file
        with open(file_path, 'w') as f:
            json.dump({
                "messages": list(messages),
                "last_cleaned": last_cleaned.isoformat()
            }, f)
            
    except Exception as e:
        print(f"Error updating user memory: {e}")

def get_conversation_history(user_id, platform):
    """Get user's conversation history"""
    file_path = get_user_file_path(user_id, platform)
    
    if not os.path.exists(file_path):
        return ""
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return "\n".join([msg['text'] for msg in data['messages']])
    except Exception as e:
        print(f"Error reading user memory: {e}")
        return ""
