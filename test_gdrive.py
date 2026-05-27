import os, sys
sys.path.insert(0, "/home/crimea_parser")
os.chdir("/home/crimea_parser")

from dotenv import load_dotenv
load_dotenv(dotenv_path="/home/crimea_parser/.env", override=True)

folder_id = os.getenv("GDRIVE_FOLDER_ID", "")
token_path = os.getenv("GDRIVE_TOKEN", "/home/crimea_parser/token.json")
print(f"FOLDER_ID:  '{folder_id}'")
print(f"TOKEN_PATH: '{token_path}'")
print(f"TOKEN_EXISTS: {os.path.exists(token_path)}")

if not folder_id:
    print("ERROR: GDRIVE_FOLDER_ID not set")
    sys.exit(1)

if not os.path.exists(token_path):
    print(f"ERROR: token.json not found at {token_path}")
    print("Run setup_gdrive_auth.py locally, then upload_gdrive_token.py")
    sys.exit(1)

from utils.gdrive import upload_file

with open("/tmp/gdrive_test.txt", "w") as f:
    f.write("Google Drive OAuth2 connection test OK")

result = upload_file("/tmp/gdrive_test.txt")
if result:
    print("SUCCESS:", result)
else:
    print("FAILED: upload returned None")
