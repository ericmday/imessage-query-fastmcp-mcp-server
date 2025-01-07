#!/usr/bin/env python3
import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, List, Any

def get_contacts_db_path() -> str:
    """Get the path to the Contacts SQLite database."""
    home = str(Path.home())
    sources_dir = os.path.join(home, "Library/Application Support/AddressBook/Sources")
    
    # Look in each directory for the AddressBook database
    for dir_name in os.listdir(sources_dir):
        dir_path = os.path.join(sources_dir, dir_name)
        if os.path.isdir(dir_path):
            db_file = os.path.join(dir_path, "AddressBook-v22.abcddb")
            if os.path.exists(db_file):
                return db_file
    
    raise FileNotFoundError("Could not find Contacts database file (AddressBook-v22.abcddb)")

def get_contacts() -> Dict[str, Dict[str, List[str]]]:
    """Get all contacts from the macOS Contacts database and format them."""
    db_path = get_contacts_db_path()
    contacts_map = {}

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query to get names, phones, and emails
    query = """
    SELECT 
        ZABCDRECORD.ZFIRSTNAME, 
        ZABCDRECORD.ZLASTNAME,
        ZABCDPHONENUMBER.ZFULLNUMBER,
        ZABCDEMAILADDRESS.ZADDRESS
    FROM ZABCDRECORD
    LEFT JOIN ZABCDPHONENUMBER ON ZABCDRECORD.Z_PK = ZABCDPHONENUMBER.ZOWNER
    LEFT JOIN ZABCDEMAILADDRESS ON ZABCDRECORD.Z_PK = ZABCDEMAILADDRESS.ZOWNER
    WHERE ZABCDRECORD.ZFIRSTNAME IS NOT NULL OR ZABCDRECORD.ZLASTNAME IS NOT NULL
    """

    cursor.execute(query)
    results = cursor.fetchall()

    # Process results
    for row in results:
        first_name = row[0] or ""
        last_name = row[1] or ""
        phone = row[2]
        email = row[3]

        # Create full name
        name = f"{first_name} {last_name}".strip()
        if not name:
            continue

        # Initialize contact if not exists
        if name not in contacts_map:
            contacts_map[name] = {
                "phones": [],
                "emails": []
            }

        # Add phone if exists and not already added
        if phone and phone not in contacts_map[name]["phones"]:
            contacts_map[name]["phones"].append(phone)

        # Add email if exists and not already added
        if email and email.lower() not in contacts_map[name]["emails"]:
            contacts_map[name]["emails"].append(email.lower())

    # Remove contacts with no phones or emails
    contacts_map = {k: v for k, v in contacts_map.items() 
                   if v["phones"] or v["emails"]}

    conn.close()
    return contacts_map

def main():
    try:
        # Get contacts
        contacts_map = get_contacts()
        
        # Write to JSON file
        with open('contacts_map.json', 'w', encoding='utf-8') as f:
            json.dump(contacts_map, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully exported {len(contacts_map)} contacts to contacts_map.json")
    
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 