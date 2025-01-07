from pathlib import Path
import os
import json
from datetime import datetime, timedelta
import imessagedb
import phonenumbers
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True  # Prevent duplicate loggers
)
logger = logging.getLogger("iMessage_Query_Test")
# Clear any existing handlers
logger.handlers = []
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.propagate = False  # Prevent duplicate logging

# Load contacts map
CONTACTS_MAP_PATH = Path(__file__).parent / "contacts_map.json"
contacts_map = {}

def load_contacts_map():
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
        raise

def lookup_contact_numbers(contact_name: str):
    """Look up phone numbers for a contact name in the contacts map."""
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

def get_messages_for_contact(contact_name: str, days_back: int = 7):
    """Get recent messages for a contact name."""
    # Default to Messages database in user's Library
    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    
    # First lookup contact's phone number
    phone_numbers = lookup_contact_numbers(contact_name)
    if not phone_numbers:
        logger.error(f"Could not find contact: {contact_name}")
        return None
        
    logger.info(f"Found numbers for {contact_name}: {phone_numbers}")
    
    # Use the first phone number (we can enhance this later)
    phone_number = phone_numbers[0]
    
    try:
        # Parse and format phone number
        parsed = phonenumbers.parse(phone_number, "US")
        if not phonenumbers.is_valid_number(parsed):
            logger.error(f"Invalid phone number for {contact_name}: {phone_number}")
            return None
        phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as e:
        logger.error(f"Could not parse phone number for {contact_name}: {e}")
        return None

    # Connect to database and get messages
    try:
        db = imessagedb.DB(str(db_path))
        messages = db.Messages("person", phone_number)
        
        # Filter to recent messages
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days_back)
        
        filtered_messages = []
        for msg in messages.message_list:
            msg_date = datetime.strptime(msg.date[:10], "%Y-%m-%d")
            if start_dt <= msg_date <= end_dt:
                filtered_messages.append({
                    "text": msg.text,
                    "date": msg.date,
                    "is_from_me": msg.is_from_me
                })
        
        return filtered_messages
        
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return None

def list_available_contacts():
    """List all available contacts in the contacts map."""
    if not contacts_map:
        load_contacts_map()
    
    print("\nAvailable contacts:")
    for name in sorted(contacts_map.keys()):
        print(f"- {name}")

def main():
    # Load contacts first
    load_contacts_map()
    
    # If no arguments, show usage and list contacts
    if len(sys.argv) < 2:
        print("Usage: python test_imessage_query.py <contact_name> [days_back]")
        print("       python test_imessage_query.py --list  (to show available contacts)")
        list_available_contacts()
        sys.exit(1)
    
    # Check if user wants to list contacts
    if sys.argv[1] == "--list":
        list_available_contacts()
        return
        
    contact_name = sys.argv[1]
    days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    
    messages = get_messages_for_contact(contact_name, days_back)
    
    if messages:
        print(f"\nFound {len(messages)} messages with {contact_name} in the last {days_back} days:\n")
        for msg in messages:
            direction = "Me" if msg["is_from_me"] else contact_name
            print(f"[{msg['date']}] {direction}: {msg['text']}")
    else:
        print(f"No messages found for {contact_name}")
        print("\nAvailable contacts that partially match:")
        contact_name_lower = contact_name.lower()
        found_matches = False
        for name in sorted(contacts_map.keys()):
            if contact_name_lower in name.lower():
                print(f"- {name}")
                found_matches = True
        if not found_matches:
            print("(No partial matches found)")

if __name__ == "__main__":
    main() 