from pathlib import Path
import os
from typing import Dict, Any, Optional, List
from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.server import InitializationOptions
from datetime import datetime, timedelta
import imessagedb
import phonenumbers
import contextlib
import io
import logging
import sys
import json
import logging.handlers

# Create logs directory if it doesn't exist
CLAUDE_LOG_PATH = Path.home() / "Library" / "Logs" / "Claude"
CLAUDE_LOG_PATH.mkdir(parents=True, exist_ok=True)

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG)  # Set root logger to DEBUG
logger = logging.getLogger("iMessage_Query")
logger.setLevel(logging.DEBUG)

# Clear any existing handlers
logger.handlers = []

# Create formatters with ISO timestamps
detailed_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03dZ [%(levelname)s] %(name)s: %(message)s',
    '%Y-%m-%dT%H:%M:%S'
)
simple_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03dZ [%(levelname)s] %(message)s',
    '%Y-%m-%dT%H:%M:%S'
)

# File handler for Claude logs
claude_handler = logging.FileHandler(
    CLAUDE_LOG_PATH / "mcp-server-iMessage_Query.log"
)
claude_handler.setFormatter(detailed_formatter)
claude_handler.setLevel(logging.INFO)

# File handler for detailed debug logs
debug_handler = logging.FileHandler(
    CLAUDE_LOG_PATH / "mcp-server-iMessage_Query_debug.log"
)
debug_handler.setFormatter(detailed_formatter)
debug_handler.setLevel(logging.DEBUG)

# Console handler for immediate feedback
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(simple_formatter)
console_handler.setLevel(logging.INFO)

# Add all handlers
logger.addHandler(claude_handler)
logger.addHandler(debug_handler)
logger.addHandler(console_handler)

logger.info("Starting iMessage Query server with enhanced logging")

# Load contacts map
CONTACTS_MAP_PATH = Path(__file__).parent / "contacts_map.json"
contacts_map: Dict[str, Dict[str, List[str]]] = {}

def load_contacts_map() -> None:
    """Load the contacts map from JSON file."""
    global contacts_map
    try:
        if CONTACTS_MAP_PATH.exists():
            with open(CONTACTS_MAP_PATH) as f:
                contacts_map = json.load(f)
            logger.info(f"Loaded contacts map with {len(contacts_map)} contacts")
        else:
            logger.warning(f"Contacts map file not found at {CONTACTS_MAP_PATH}")
    except Exception as e:
        logger.error(f"Error loading contacts map: {e}")

# Define prompts first
MESSAGES_PROMPT = """You are an AI assistant that helps users access their iMessage chat history.

CRITICAL INSTRUCTION: When a user asks for messages with a contact, you MUST IMMEDIATELY execute get_chat_transcript with the contact name. DO NOT ask for phone numbers or any additional information.

Example:
User: "Show me messages with Matthew Day"
You must immediately execute:
get_chat_transcript(contact="Matthew Day")

User: "What did John text me yesterday?"
You must immediately execute:
get_chat_transcript(contact="John")

DO NOT:
- Ask for phone numbers
- Explain the process
- Request additional information
- Show any intermediate steps

Just execute get_chat_transcript immediately with the contact name."""

try:
    # Load contacts map before server initialization
    logger.info("Initializing server components...")
    load_contacts_map()
    logger.debug("Contacts map loaded successfully")

    logger.info("Creating FastMCP instance...")
    # Create FastMCP instance with configuration
    mcp = FastMCP(
        "iMessage_Query",
        dependencies=["imessagedb", "phonenumbers", str(CONTACTS_MAP_PATH)],
        system_prompt=MESSAGES_PROMPT,
        prompts={"get_chat_transcript": MESSAGES_PROMPT},
        server_options=InitializationOptions(
            server_name="iMessage_Query",
            server_version="0.1.0",
            capabilities={
                "transport": "stdio",
                "keep_alive": True,
                "log_level": "INFO"
            }
        )
    )
    logger.info("FastMCP instance created successfully with configuration")

except Exception as e:
    logger.error(f"Failed to initialize server: {e}", exc_info=True)
    sys.exit(1)

# Default to Messages database in user's Library
DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"
DB_PATH = Path(os.environ.get('SQLITE_DB_PATH', DEFAULT_DB_PATH))

def lookup_contact_numbers(contact_name: str) -> Optional[List[str]]:
    """Look up phone numbers for a contact name in the contacts map.
    
    Args:
        contact_name: Name of the contact to look up
        
    Returns:
        List of phone numbers if found, None otherwise
    """
    if not contacts_map:
        load_contacts_map()
        
    # Try exact match first
    if contact_name in contacts_map:
        return contacts_map[contact_name].get("phones", [])
        
    # Try case-insensitive partial match
    contact_name_lower = contact_name.lower()
    for name, info in contacts_map.items():
        if contact_name_lower in name.lower():
            return info.get("phones", [])
            
    return None

# Register the tool
@mcp.tool()
def get_chat_transcript(
    contact: str,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """Get chat transcript for a contact (name or phone number) within a date range."""
    logger.debug(f"get_chat_transcript called with contact={contact}, start_date={start_date}, end_date={end_date}")
    
    # First try to lookup contact in contacts map
    contact_numbers = lookup_contact_numbers(contact)
    if not contact_numbers:
        # If no contact found, check if input is already a phone number
        try:
            parsed = phonenumbers.parse(contact, "US")
            if phonenumbers.is_valid_number(parsed):
                contact_numbers = [phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)]
                logger.debug(f"Input was a valid phone number: {contact_numbers[0]}")
            else:
                logger.error(f"Could not find contact '{contact}' in contacts map and input is not a valid phone number")
                raise ValueError(f"Could not find contact '{contact}' in contacts map and input is not a valid phone number")
        except phonenumbers.NumberParseException:
            logger.error(f"Could not find contact '{contact}' in contacts map")
            raise ValueError(f"Could not find contact '{contact}' in contacts map")
        
    logger.debug(f"Found contact {contact} with numbers: {contact_numbers}")
    
    # Get messages using the first valid phone number found
    phone_number = contact_numbers[0]  # Use first number for now
    
    # Format the phone number to E.164
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"Invalid phone number: {phone_number}")
        phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        logger.debug(f"Formatted phone number: {phone_number}")
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Invalid phone number format: {e}")

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")

    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        with MessageDBConnection() as db:
            # Create Messages object for the phone number
            messages = db.Messages("person", phone_number, numbers=[phone_number])
            
            # Set default date range to last 7 days if not specified
            if not start_date and not end_date:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=7)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            
            # Filter messages by date if specified
            filtered_messages = []
            for msg in messages.message_list:
                msg_date = datetime.strptime(msg.date[:10], "%Y-%m-%d")
                
                if start_date:
                    start_dt = datetime.fromisoformat(start_date)
                    if msg_date < start_dt:
                        continue
                        
                if end_date:
                    end_dt = datetime.fromisoformat(end_date)
                    if msg_date > end_dt:
                        continue
                        
                filtered_messages.append({
                    "text": str(msg.text) if msg.text else "",
                    "date": msg.date,
                    "is_from_me": bool(msg.is_from_me),
                    "has_attachments": bool(msg.attachments),
                    "attachments": [
                        {
                            "mime_type": att.mime_type if hasattr(att, 'mime_type') else None,
                            "filename": att.filename if hasattr(att, 'filename') else None,
                            "file_path": att.original_path if hasattr(att, 'original_path') else None,
                            "is_missing": att.missing if hasattr(att, 'missing') else False
                        } for att in msg.attachments if isinstance(att, object)
                    ] if msg.attachments else []
                })
            
            return {
                "messages": filtered_messages,
                "total_count": len(filtered_messages)
            }

class DatabaseContext:
    """Singleton context for managing database connections across tools."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseContext, cls).__new__(cls)
            cls._instance.db_path = DB_PATH
            cls._instance._db = None
        return cls._instance
    
    def get_connection(self):
        """Get an imessagedb connection from the context."""
        if self._db is None:
            self._db = imessagedb.DB(str(self.db_path))
        return self._db

class MessageDBConnection:
    """Context manager for database connections."""
    def __init__(self):
        self.db_context = DatabaseContext()
        self.db = None
        
    def __enter__(self):
        self.db = self.db_context.get_connection()
        return self.db
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # No need to close imessagedb connection
        pass

if __name__ == "__main__":
    try:
        # Verify database exists
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")
            
        logger.info(f"Starting iMessage Query server...")
        logger.info(f"Using database at: {DB_PATH}")
        logger.info(f"Contacts map path: {CONTACTS_MAP_PATH}")
        logger.debug("Server configuration complete, starting MCP server...")
        
        # Start the FastMCP server with stdio transport
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Server shutdown complete")