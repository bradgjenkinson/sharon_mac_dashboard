"""
XeroClient - High-level wrapper around the Xero Accounting API.

Uses the official xero-python SDK for structured responses, but also
exposes a raw `get()` / `post()` for direct API calls when needed.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from .auth import XeroAuth

load_dotenv()

BASE_URL = "https://api.xero.com/api.xro/2.0"


class XeroClient:
    """Thin wrapper that injects auth headers and tenant ID into every request."""

    def __init__(self, auth: XeroAuth | None = None):
        self.auth = auth or XeroAuth()
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _headers(self, accept: str = "application/json") -> dict:
        return {
            "Authorization": f"Bearer {self.auth.get_token()}",
            "Xero-Tenant-Id": self.auth.get_tenant_id(),
            "Accept": accept,
        }

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        accept: str = "application/json",
    ) -> Any:
        """
        Perform a GET request against the Xero Accounting API.

        Args:
            endpoint: Path after /api.xro/2.0/, e.g. "Invoices" or "Contacts/abc123"
            params:   Query-string parameters dict
            accept:   MIME type (default JSON; use "application/pdf" for PDF exports)

        Returns:
            Parsed JSON dict (or raw bytes for non-JSON accepts).
        """
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = self._session.get(url, headers=self._headers(accept), params=params, timeout=30)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        return resp.content

    def post(self, endpoint: str, payload: dict) -> Any:
        """
        Perform a POST/PUT request against the Xero Accounting API.

        Args:
            endpoint: Path after /api.xro/2.0/
            payload:  Dict to send as JSON body

        Returns:
            Parsed JSON response dict.
        """
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = self._session.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Convenience methods — Accounts
    # ------------------------------------------------------------------

    def get_accounts(self, **kwargs) -> list[dict]:
        """Return all accounts in the chart of accounts."""
        data = self.get("Accounts", params=kwargs)
        return data.get("Accounts", [])

    # ------------------------------------------------------------------
    # Convenience methods — Contacts
    # ------------------------------------------------------------------

    def get_contacts(self, **kwargs) -> list[dict]:
        """Return all contacts (customers & suppliers)."""
        data = self.get("Contacts", params=kwargs)
        return data.get("Contacts", [])

    def get_contact(self, contact_id: str) -> dict:
        """Return a single contact by ID."""
        data = self.get(f"Contacts/{contact_id}")
        contacts = data.get("Contacts", [])
        return contacts[0] if contacts else {}

    # ------------------------------------------------------------------
    # Convenience methods — Invoices
    # ------------------------------------------------------------------

    def get_invoices(self, **kwargs) -> list[dict]:
        """
        Return invoices.  Common kwargs:
          Statuses='AUTHORISED,PAID'
          ContactIDs='...'
          DateFrom='2024-01-01'
          DateTo='2024-12-31'
          page=1  (100 per page)
        """
        data = self.get("Invoices", params=kwargs)
        return data.get("Invoices", [])

    def get_invoice(self, invoice_id: str) -> dict:
        """Return a single invoice by ID."""
        data = self.get(f"Invoices/{invoice_id}")
        invoices = data.get("Invoices", [])
        return invoices[0] if invoices else {}

    def get_invoice_pdf(self, invoice_id: str) -> bytes:
        """Download an invoice as PDF bytes."""
        return self.get(f"Invoices/{invoice_id}", accept="application/pdf")

    # ------------------------------------------------------------------
    # Convenience methods — Bank Transactions
    # ------------------------------------------------------------------

    def get_bank_transactions(self, **kwargs) -> list[dict]:
        """Return bank transactions."""
        data = self.get("BankTransactions", params=kwargs)
        return data.get("BankTransactions", [])

    # ------------------------------------------------------------------
    # Convenience methods — Reports
    # ------------------------------------------------------------------

    def get_profit_and_loss(self, from_date: str, to_date: str) -> dict:
        """Return the Profit & Loss report for a date range (YYYY-MM-DD)."""
        return self.get(
            "Reports/ProfitAndLoss",
            params={"fromDate": from_date, "toDate": to_date},
        )

    def get_balance_sheet(self, date: str) -> dict:
        """Return the Balance Sheet as at a given date (YYYY-MM-DD)."""
        return self.get("Reports/BalanceSheet", params={"date": date})

    def get_trial_balance(self, date: str) -> dict:
        """Return the Trial Balance as at a given date (YYYY-MM-DD)."""
        return self.get("Reports/TrialBalance", params={"date": date})

    def get_aged_receivables(self, contact_id: str | None = None) -> dict:
        """Return the Aged Receivables report."""
        params = {"contactID": contact_id} if contact_id else {}
        return self.get("Reports/AgedReceivablesByContact", params=params)

    def get_aged_payables(self, contact_id: str | None = None) -> dict:
        """Return the Aged Payables report."""
        params = {"contactID": contact_id} if contact_id else {}
        return self.get("Reports/AgedPayablesByContact", params=params)

    # ------------------------------------------------------------------
    # Convenience methods — Journals
    # ------------------------------------------------------------------

    def get_journals(self, offset: int = 0) -> list[dict]:
        """Return journals (max 100 per call; use offset to paginate)."""
        data = self.get("Journals", params={"offset": offset})
        return data.get("Journals", [])

    # ------------------------------------------------------------------
    # Convenience methods — Organisation
    # ------------------------------------------------------------------

    def get_organisation(self) -> dict:
        """Return the connected organisation's details."""
        data = self.get("Organisation")
        orgs = data.get("Organisations", [])
        return orgs[0] if orgs else {}
