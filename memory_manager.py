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

def update_user_memory(platform, user_id, message):
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
        
        # Add new message with timestamp
        messages.append({
            "timestamp": datetime.now().isoformat(),
            "message": message
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
    """Get conversation history for a user"""
    filename = get_memory_filename(platform, user_id)
    
    if not os.path.exists(filename):
        return ""
    
    try:
        with open(filename, 'r') as f:
            messages = json.load(f)
        
        # Format messages without "User/AI:" prefix
        formatted = []
        for msg in messages:
            # Remove any role prefix (User/AI:) from the message
            message_text = msg['message']
            if message_text.startswith(("User:", "AI:")):
                message_text = message_text.split(":", 1)[1].strip()
            formatted.append(message_text)
            
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
