"""Upload files to Google Drive using a service account.

Required env vars:
  GDRIVE_FOLDER_ID  — ID of the Drive folder to upload into
                      (last part of https://drive.google.com/drive/folders/<ID>)
  GDRIVE_CREDENTIALS — path to service_account credentials.json
                       (default: /opt/hotel_lead_bot/credentials.json)

Setup (one-time):
  1. In Google Cloud Console, enable Drive API for the service account project.
  2. Share the target Drive folder with the service account email (Editor role).
  3. Set GDRIVE_FOLDER_ID in .env.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_CREDS = "/opt/hotel_lead_bot/credentials.json"


def upload_file(local_path: str, folder_id: str | None = None) -> str | None:
    """
    Upload a local file to Google Drive.
    Returns the web view URL on success, None on failure.
    If folder_id is not provided, reads GDRIVE_FOLDER_ID from env.
    """
    folder_id = folder_id or os.getenv("GDRIVE_FOLDER_ID", "")
    if not folder_id:
        print("[gdrive] GDRIVE_FOLDER_ID not set — skipping upload")
        return None

    creds_path = os.getenv("GDRIVE_CREDENTIALS", _DEFAULT_CREDS)
    if not os.path.exists(creds_path):
        print(f"[gdrive] credentials.json not found: {creds_path}")
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        file_name = Path(local_path).name
        if local_path.endswith(".xlsx"):
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            mime = "text/csv"

        # Update existing file with same name in folder, or create new
        existing = (
            service.files()
            .list(
                q=f"name='{file_name}' and '{folder_id}' in parents and trashed=false",
                fields="files(id)",
            )
            .execute()
            .get("files", [])
        )

        media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
        if existing:
            file_id = existing[0]["id"]
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            meta = {"name": file_name, "parents": [folder_id]}
            result = service.files().create(
                body=meta, media_body=media, fields="id"
            ).execute()
            file_id = result["id"]

        link = f"https://drive.google.com/file/d/{file_id}/view"
        print(f"[gdrive] uploaded: {file_name} → {link}")
        return link

    except Exception as e:
        print(f"[gdrive] upload error for {local_path}: {e}")
        return None
