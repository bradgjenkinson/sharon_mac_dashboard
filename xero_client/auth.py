"""
XeroAuth - Handles OAuth 2.0 PKCE flow for desktop/script use.

Flow:
  1. Generates an authorization URL and opens it in the browser.
  2. Spins up a temporary localhost server to capture the redirect callback.
  3. Exchanges the authorization code for access + refresh tokens.
  4. Persists tokens to disk and auto-refreshes when expired.
"""

import json
import os
import secrets
import hashlib
import base64
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

# Search for .env from the project root (parent of xero_client/) upward
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)
load_dotenv(_PROJECT_ROOT / "dashboard" / ".env", override=False)

TOKEN_URL = "https://identity.xero.com/connect/token"
AUTH_URL = "https://login.xero.com/identity/connect/authorize"
CONNECTIONS_URL = "https://api.xero.com/connections"


class XeroAuth:
    """Manages OAuth 2.0 tokens for the Xero API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        scopes: str | None = None,
        token_file: str | Path = "tokens/xero_tokens.json",
    ):
        self.client_id = client_id or os.environ["XERO_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["XERO_CLIENT_SECRET"]
        self.redirect_uri = redirect_uri or os.environ.get(
            "XERO_REDIRECT_URI", "http://localhost:8080/callback"
        )
        self.scopes = scopes or os.environ.get(
            "XERO_SCOPES",
            "openid profile email offline_access accounting.contacts.read accounting.invoices.read accounting.settings.read",
        )
        self.token_file = Path(token_file)
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self._tokens: dict = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_token(self) -> str:
        """Return a valid access token, refreshing or re-authorizing as needed."""
        self._load_tokens()
        if self._tokens and not self._is_expired():
            return self._tokens["access_token"]
        if self._tokens.get("refresh_token"):
            self._refresh()
            return self._tokens["access_token"]
        # Full authorization required
        self._authorize()
        return self._tokens["access_token"]

    def get_tenant_id(self) -> str:
        """Return the persisted tenant (organisation) ID."""
        self._load_tokens()
        tenant_id = self._tokens.get("tenant_id")
        if not tenant_id:
            raise RuntimeError(
                "No tenant_id stored. Run get_token() to complete authorization first."
            )
        return tenant_id

    def revoke(self) -> None:
        """Delete the stored tokens (forces re-authorization next time)."""
        if self.token_file.exists():
            self.token_file.unlink()
        self._tokens = {}
        print("Tokens revoked.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _authorize(self) -> None:
        """Run the PKCE authorization code flow."""
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(16)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{AUTH_URL}?{urlencode(params)}"

        # Capture the redirect on a local HTTP server
        callback_data: dict = {}
        parsed = urlparse(self.redirect_uri)
        port = parsed.port or 8080

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default logging
                pass

            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                callback_data["code"] = qs.get("code", [None])[0]
                callback_data["state"] = qs.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h2>Authorization successful! You can close this window.</h2>"
                )

        server = HTTPServer(("localhost", port), _Handler)

        def _serve():
            server.handle_request()

        thread = threading.Thread(target=_serve, daemon=True)
        thread.start()

        print(f"\nOpening browser for Xero authorization...\n{auth_url}\n")
        webbrowser.open(auth_url)
        thread.join(timeout=120)

        if not callback_data.get("code"):
            raise RuntimeError("Authorization timed out or was cancelled.")
        if callback_data.get("state") != state:
            raise RuntimeError("State mismatch — possible CSRF attack.")

        # Exchange code for tokens
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": callback_data["code"],
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": code_verifier,
            },
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        self._store_tokens(resp.json())
        self._fetch_and_store_tenant()
        print("Authorization complete. Tokens saved.")

    def _refresh(self) -> None:
        """Use the refresh token to get a new access token."""
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._tokens["refresh_token"],
            },
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        if resp.status_code == 400:
            print("Refresh token expired. Re-authorizing...")
            self._tokens = {}
            self._authorize()
            return
        resp.raise_for_status()
        # Preserve tenant_id across refresh
        tenant_id = self._tokens.get("tenant_id")
        self._store_tokens(resp.json())
        if tenant_id and not self._tokens.get("tenant_id"):
            self._tokens["tenant_id"] = tenant_id
            self._save_tokens()

    def _fetch_and_store_tenant(self) -> None:
        """Fetch available tenants and persist the first one."""
        resp = requests.get(
            CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {self._tokens['access_token']}"},
            timeout=30,
        )
        resp.raise_for_status()
        tenants = resp.json()
        if not tenants:
            raise RuntimeError("No Xero organisations connected to this app.")
        if len(tenants) > 1:
            print("\nMultiple organisations found:")
            for i, t in enumerate(tenants):
                print(f"  [{i}] {t['tenantName']} ({t['tenantId']})")
            idx = int(input("Select organisation number: "))
        else:
            idx = 0
        self._tokens["tenant_id"] = tenants[idx]["tenantId"]
        self._tokens["tenant_name"] = tenants[idx]["tenantName"]
        self._save_tokens()
        print(f"Connected to: {tenants[idx]['tenantName']}")

    def _store_tokens(self, data: dict) -> None:
        now = datetime.now(timezone.utc).timestamp()
        self._tokens.update(
            {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", self._tokens.get("refresh_token")),
                "expires_at": now + data.get("expires_in", 1800),
            }
        )
        self._save_tokens()

    def _save_tokens(self) -> None:
        with open(self.token_file, "w") as f:
            json.dump(self._tokens, f, indent=2)

    def _load_tokens(self) -> None:
        if self.token_file.exists() and not self._tokens:
            with open(self.token_file) as f:
                self._tokens = json.load(f)

    def _is_expired(self) -> bool:
        expires_at = self._tokens.get("expires_at", 0)
        # Consider expired 60 seconds early
        return datetime.now(timezone.utc).timestamp() >= expires_at - 60
