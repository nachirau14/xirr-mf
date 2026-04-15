"""
API Client — communicates with the AWS Lambda API Gateway backend.
All API calls go through this module.
"""
import streamlit as st
import requests
import json
from functools import wraps
from datetime import datetime


def get_api_base():
    return st.secrets.get("API_BASE_URL", "").rstrip("/")


def get_user_id():
    return st.session_state.get("user_id", "default_user")


def api_call(method, path, params=None, json_body=None, timeout=30, silent=False):
    """Generic API call with error handling.
    silent=True suppresses st.error for 404/cache-miss responses.
    """
    base = get_api_base()
    if not base:
        st.error("API_BASE_URL not configured in secrets.")
        return None

    url = f"{base}{path}"
    try:
        resp = requests.request(
            method, url,
            params=params,
            json=json_body,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        # Treat 404 on GET as a cache miss — return None silently
        if resp.status_code == 404 and method == "GET":
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        if not silent:
            st.error("Request timed out. Please try again.")
        return None
    except requests.exceptions.HTTPError as e:
        if not silent:
            st.error(f"API Error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        if not silent:
            st.error(f"Connection error: {e}")
        return None


class APIClient:
    
    # ─── Investments ──────────────────────────────────────────────────────
    
    @staticmethod
    def get_investments(inv_type=None, category=None):
        params = {"user_id": get_user_id()}
        if inv_type:
            params["type"] = inv_type
        if category:
            params["category"] = category
        return api_call("GET", "/investments", params=params)
    
    @staticmethod
    def create_investment(data: dict):
        data["user_id"] = get_user_id()
        return api_call("POST", "/investments", json_body=data)
    
    @staticmethod
    def update_investment(investment_id: str, data: dict):
        data["user_id"] = get_user_id()
        return api_call("PUT", f"/investments/{investment_id}", json_body=data)
    
    @staticmethod
    def delete_investment(investment_id: str):
        return api_call("DELETE", f"/investments/{investment_id}",
                        params={"user_id": get_user_id()})
    
    # ─── Transactions ─────────────────────────────────────────────────────
    
    @staticmethod
    def get_transactions(investment_id: str):
        return api_call("GET", "/transactions", params={"investment_id": investment_id})
    
    @staticmethod
    def add_transaction(txn: dict):
        return api_call("POST", "/transactions", json_body=txn)
    
    @staticmethod
    def bulk_add_transactions(transactions: list):
        return api_call("POST", "/transactions",
                        json_body={"transactions": transactions})
    
    @staticmethod
    def delete_transaction(investment_id: str, txn_id: str):
        return api_call("DELETE", f"/transactions/{txn_id}",
                        params={"investment_id": investment_id})
    
    # ─── XIRR ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def calculate_xirr(investment_ids=None):
        body = {"user_id": get_user_id()}
        if investment_ids:
            body["investment_ids"] = investment_ids
        return api_call("POST", "/xirr", json_body=body)
    
    @staticmethod
    def get_cached_xirr(investment_id: str):
        # silent=True: 404 = not yet calculated, not an error
        return api_call("GET", "/xirr",
                        params={"user_id": get_user_id(), "investment_id": investment_id},
                        silent=True)
    
    # ─── NAV ──────────────────────────────────────────────────────────────
    
    @staticmethod
    def get_nav_history(scheme_code: str, from_date: str = None, to_date: str = None):
        params = {"scheme_code": scheme_code}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        return api_call("GET", "/nav", params=params)
    
    @staticmethod
    def add_manual_nav(investment_id: str, nav_date: str, nav_value: float, total_value: float = None):
        return api_call("POST", "/manual-nav", json_body={
            "user_id": get_user_id(),
            "investment_id": investment_id,
            "nav_date": nav_date,
            "nav_value": nav_value,
            "total_value": total_value
        })
    
    # ─── Scheme Search ────────────────────────────────────────────────────
    
    @staticmethod
    def search_scheme(query: str):
        return api_call("GET", "/search-scheme", params={"q": query})
    
    # ─── NAV Fetch Trigger ────────────────────────────────────────────────

    @staticmethod
    def trigger_nav_fetch(scheme_codes: list = None):
        """Invoke the NAV fetcher Lambda via API for specific or all schemes."""
        body = {"user_id": get_user_id()}
        if scheme_codes:
            body["scheme_codes"] = scheme_codes
        return api_call("POST", "/nav-fetch", json_body=body, silent=True)

    # ─── Analytics ────────────────────────────────────────────────────────

    @staticmethod
    def get_analytics():
        return api_call("GET", "/analytics", params={"user_id": get_user_id()})
