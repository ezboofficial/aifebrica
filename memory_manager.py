import os
import json
from datetime import datetime
from github import Github
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MEMORY_DIR = "chatsmemory"
MAX_MESSAGES = 30

def ensure_memory_dir():
    """Ensure the memory directory exists"""
    if not os.path.exists(MEMORY_DIR):
        os.makedirs(MEMORY_DIR)

def get_memory_filename(platform, user_id):
    """Generate memory filename for a user"""
    return os.path.join(MEMORY_DIR, f"{platform}_{user_id}_chats.json")

def update_user_memory(platform, user_id, message, is_user=None):
    """Update user memory with a new message"""
    ensure_memory_dir()
    filename = get_memory_filename(platform, user_id)
    
    try:
        # Load existing messages
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                messages = json.load(f)
        else:
            messages = []
        
        # Determine role if not explicitly provided
        if is_user is None:
            is_user = not any([
                message.startswith(("[", "AI:")),
                message.startswith(("Hi there!", "I'm doing great", "Okay", "That's", 
                                  "For order changes", "I'm sorry", "Sorry", "Please",
                                  "How can I help", "Here is", "You can", "We have"))
            ])
        
        # Clean message by removing any existing role prefixes
        clean_message = message
        if clean_message.startswith("AI:"):
            clean_message = clean_message[3:].strip()
        elif clean_message.startswith("User:"):
            clean_message = clean_message[5:].strip()
        
        # Add new message with timestamp and role
        messages.append({
            "timestamp": datetime.now().isoformat(),
            "role": "User" if is_user else "AI",
            "message": clean_message
        })
        
        # Keep only the last MAX_MESSAGES
        messages = messages[-MAX_MESSAGES:]
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(messages, f, indent=2)
            
        # Update GitHub repository
        update_github_repo(filename, messages)
        
    except Exception as e:
        logger.error(f"Error updating user memory: {str(e)}")

def get_conversation_history(platform, user_id):
    """Get conversation history for a user in the desired format"""
    filename = get_memory_filename(platform, user_id)
    
    if not os.path.exists(filename):
        return ""
    
    try:
        with open(filename, 'r') as f:
            messages = json.load(f)
        
        # Format messages as "User: message" or "AI: message"
        formatted = []
        for msg in messages:
            # Clean up message by removing any existing role prefixes
            clean_msg = msg['message']
            if clean_msg.startswith("AI:"):
                clean_msg = clean_msg[3:].strip()
            elif clean_msg.startswith("User:"):
                clean_msg = clean_msg[5:].strip()
                
            formatted.append(f"{msg['role']}: {clean_msg}")
            
        return "\n".join(formatted)
    
    except Exception as e:
        logger.error(f"Error reading conversation history: {str(e)}")
        return ""

def update_github_repo(filename, content):
    """Update GitHub repository with memory changes"""
    try:
        github = Github(os.getenv("GITHUB_ACCESS_TOKEN"))
        repo = github.get_repo(os.getenv("GITHUB_REPO_NAME"))
        
        # Convert content to string if it's not already
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        
        # Try to get the file first
        try:
            file_content = repo.get_contents(filename)
            repo.update_file(
                path=filename,
                message="Update chat memory via chatbot",
                content=content,
                sha=file_content.sha
            )
        except Exception as e:
            if "404" in str(e):  # File doesn't exist
                repo.create_file(
                    path=filename,
                    message="Initialize chat memory file",
                    content=content,
                    branch="main"
                )
        
        logger.info(f"GitHub repository updated with memory changes for {filename}")
    except Exception as e:
        logger.error(f"Failed to update GitHub repository with memory changes: {str(e)}")

def clear_conversation_history(platform, user_id):
    """Clear conversation history for a user"""
    filename = get_memory_filename(platform, user_id)
    try:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"Cleared conversation history for {platform} user {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error clearing conversation history: {str(e)}")
        return False

def get_raw_conversation_history(platform, user_id):
    """Get raw conversation history with all metadata"""
    filename = get_memory_filename(platform, user_id)
    
    if not os.path.exists(filename):
        return []
    
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading raw conversation history: {str(e)}")
        return []

def backup_conversation_history(platform, user_id, backup_dir="memory_backups"):
    """Create a backup of conversation history"""
    try:
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        filename = get_memory_filename(platform, user_id)
        if not os.path.exists(filename):
            return False
            
        backup_filename = os.path.join(
            backup_dir,
            f"{platform}_{user_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        with open(filename, 'r') as original, open(backup_filename, 'w') as backup:
            backup.write(original.read())
            
        logger.info(f"Created backup of conversation history at {backup_filename}")
        return True
    except Exception as e:
        logger.error(f"Error creating conversation backup: {str(e)}")
        return False
