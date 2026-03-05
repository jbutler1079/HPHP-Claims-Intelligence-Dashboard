"""
onedrive_sync.py
Syncs master CSV files between Render's ephemeral filesystem and OneDrive
using the Microsoft Graph API with app-only (client credentials) auth.

Required Render environment variables
--------------------------------------
ONEDRIVE_CLIENT_ID      – Azure App Registration client ID
ONEDRIVE_CLIENT_SECRET  – Azure App Registration client secret
ONEDRIVE_TENANT_ID      – Azure AD tenant ID
ONEDRIVE_USER_EMAIL     – OneDrive owner email (e.g. you@yourdomain.com)
ONEDRIVE_FOLDER_PATH    – Destination folder in OneDrive (default: HPHP Claims Data)

Azure App Registration permissions required
--------------------------------------------
Microsoft Graph → Application permissions → Files.ReadWrite.All
(Grant admin consent after adding the permission.)
"""

import logging
import os

import msal
import requests

logger = logging.getLogger(__name__)

_CLIENT_ID     = os.environ.get("ONEDRIVE_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("ONEDRIVE_CLIENT_SECRET", "")
_TENANT_ID     = os.environ.get("ONEDRIVE_TENANT_ID", "")
_USER_EMAIL    = os.environ.get("ONEDRIVE_USER_EMAIL", "")
_FOLDER_PATH   = os.environ.get("ONEDRIVE_FOLDER_PATH", "HPHP Claims Data")

GRAPH_BASE    = "https://graph.microsoft.com/v1.0"
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# Maps file_type key → filename on disk and in OneDrive
_MASTER_FILES = {
    "medical":  "medical_claims_master.csv",
    "pharmacy": "pharmacy_claims_master.csv",
    "members":  "members_master.csv",
}


def _is_configured() -> bool:
    return all([_CLIENT_ID, _CLIENT_SECRET, _TENANT_ID, _USER_EMAIL])


def _get_token() -> str:
    """Acquire an app-only access token via the client credentials flow."""
    app = msal.ConfidentialClientApplication(
        client_id=_CLIENT_ID,
        client_credential=_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{_TENANT_ID}",
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"MSAL token acquisition failed: {result.get('error_description', result)}"
        )
    return result["access_token"]


def _content_url(filename: str) -> str:
    return (
        f"{GRAPH_BASE}/users/{_USER_EMAIL}/drive"
        f"/root:/{_FOLDER_PATH}/{filename}:/content"
    )


def _session_url(filename: str) -> str:
    return (
        f"{GRAPH_BASE}/users/{_USER_EMAIL}/drive"
        f"/root:/{_FOLDER_PATH}/{filename}:/createUploadSession"
    )


def _upload_via_session(token: str, filename: str, data: bytes) -> None:
    """
    Use a Graph resumable upload session so any file size is handled correctly.
    (Simple PUT is limited to 4 MB; upload sessions handle up to 60 MB per chunk.)
    """
    session_resp = requests.post(
        _session_url(filename),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        timeout=30,
    )
    if session_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create upload session for {filename}: {session_resp.text}"
        )

    upload_url = session_resp.json()["uploadUrl"]
    total = len(data)

    put_resp = requests.put(
        upload_url,
        headers={
            "Content-Length": str(total),
            "Content-Range": f"bytes 0-{total - 1}/{total}",
            "Content-Type": "text/csv",
        },
        data=data,
        timeout=120,
    )
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Upload session PUT failed for {filename}: "
            f"{put_resp.status_code} {put_resp.text}"
        )


# ── Public API ────────────────────────────────────────────────────────────────

def download_masters() -> None:
    """
    Pull master CSVs from OneDrive to the local processed/ directory.
    Called once at API server startup to restore state on Render's ephemeral disk.
    Errors are logged and suppressed so the server always starts successfully.
    """
    if not _is_configured():
        logger.info("OneDrive sync not configured — skipping startup download.")
        return

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    try:
        token = _get_token()
    except Exception as exc:
        logger.error("OneDrive: failed to acquire token on startup: %s", exc)
        return

    for _key, fname in _MASTER_FILES.items():
        try:
            resp = requests.get(
                _content_url(fname),
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            if resp.status_code == 200:
                local = os.path.join(PROCESSED_DIR, fname)
                with open(local, "wb") as fh:
                    fh.write(resp.content)
                logger.info(
                    "OneDrive → local: %s (%d bytes)", fname, len(resp.content)
                )
            elif resp.status_code == 404:
                logger.info(
                    "OneDrive: %s not found yet (first run — will be created on first upload).",
                    fname,
                )
            else:
                logger.warning(
                    "OneDrive: unexpected status %d downloading %s: %s",
                    resp.status_code,
                    fname,
                    resp.text,
                )
        except Exception as exc:
            logger.error("OneDrive: error downloading %s: %s", fname, exc)


def upload_master(file_type: str) -> None:
    """
    Push an updated master CSV to OneDrive after a successful ingestion.
    file_type must be one of: 'medical', 'pharmacy', 'members'.
    Errors are logged and suppressed so a sync failure never blocks the upload response.
    """
    if not _is_configured():
        return

    fname = _MASTER_FILES.get(file_type)
    if not fname:
        return

    local = os.path.join(PROCESSED_DIR, fname)
    if not os.path.exists(local):
        return

    try:
        token = _get_token()
        with open(local, "rb") as fh:
            data = fh.read()
        _upload_via_session(token, fname, data)
        logger.info("Local → OneDrive: %s (%d bytes)", fname, len(data))
    except Exception as exc:
        logger.error("OneDrive: error uploading %s: %s", fname, exc)
