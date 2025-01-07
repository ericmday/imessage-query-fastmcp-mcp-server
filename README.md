# macOS Contacts and iMessage Query Tools

A collection of Python tools for safely accessing and exporting data from macOS Contacts and iMessage databases. This includes tools for exporting contacts to JSON format and querying iMessage conversations.

## 📋 System Requirements

- macOS (required for Contacts and iMessage database access)
- Python 3.6+

## 📦 Dependencies

Install all required dependencies:

```bash
pip install -r requirements.txt
```

### Required Packages
- **imessagedb**: Python library for accessing and querying the macOS Messages database
- **phonenumbers**: Google's phone number handling library for proper number validation and formatting

All dependencies are specified in `requirements.txt` for easy installation.

## 📑️ Features

### Contacts Export
The `export_contacts.py` script provides:
- Export of all macOS Contacts to JSON format
- Phone numbers and email addresses for each contact
- Proper handling of multiple phone numbers/emails per contact
- Unicode character support
- Maintains original phone number formatting
- Filters out contacts with no phone or email

### iMessage Query
Support for querying iMessage conversations with:
- Lookup by name
- Message history retrieval
- Attachment information
- Date range filtering
- Phone number validation

## 🚀 Getting Started

1. Clone the repository:
```bash
git clone https://github.com/yourusername/immesage-query-mcp-server.git
cd immesage-query-mcp-server
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Export your contacts:
```bash
python export_contacts.py
```

This will create a `contacts_map.json` file with all your contacts in the following format:
```json
{
  "Contact Name": {
    "phones": [
      "+1234567890",
      "123-456-7890"
    ],
    "emails": [
      "email@example.com"
    ]
  }
}
```

## 🔒 Safety Features

- Read-only access to system databases
- No modification of original data
- Safe handling of Unicode characters
- Duplicate entry prevention
- Error handling for missing or inaccessible files

## ⚙️ System Access Requirements

The script requires access to:
- `~/Library/Application Support/AddressBook/Sources/`: Location of the Contacts database
- Terminal/IDE needs "Full Disk Access" in System Preferences > Security & Privacy > Privacy

## 📚 Development

The main components are:
- `export_contacts.py`: Script for exporting contacts to JSON
- `requirements.txt`: Project dependencies
- `contacts_map.json`: Generated contacts export file