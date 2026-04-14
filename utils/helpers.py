"""
Shared utilities for the Streamlit frontend.
Includes local XIRR calculation for instant UI feedback.
"""
import streamlit as st
from datetime import datetime
from decimal import Decimal

INVESTMENT_TYPES = ["MF", "AIF", "PMS"]

MF_CATEGORIES = [
    "Equity - Large Cap",
    "Equity - Mid Cap",
    "Equity - Small Cap",
    "Equity - Flexi Cap",
    "Equity - Multi Cap",
    "Equity - Sectoral/Thematic",
    "ELSS (Tax Saving)",
    "Debt - Liquid",
    "Debt - Ultra Short Duration",
    "Debt - Short Duration",
    "Debt - Medium Duration",
    "Debt - Long Duration",
    "Debt - Gilt",
    "Debt - Corporate Bond",
    "Debt - Credit Risk",
    "Debt - Dynamic Bond",
    "Hybrid - Aggressive",
    "Hybrid - Balanced",
    "Hybrid - Conservative",
    "Hybrid - Arbitrage",
    "Index Fund",
    "International Fund",
    "FOF (Fund of Funds)",
    "Other",
]

AIF_CATEGORIES = [
    "Category I - Venture Capital",
    "Category I - Infrastructure",
    "Category I - Social Venture",
    "Category II - Private Equity",
    "Category II - Debt",
    "Category II - Real Estate",
    "Category III - Long Only",
    "Category III - Long Short",
    "Other",
]

PMS_CATEGORIES = [
    "Equity PMS",
    "Debt PMS",
    "Multi Asset PMS",
    "Quant / Algo PMS",
    "Other",
]

TXN_TYPES = ["BUY", "SELL", "DIVIDEND", "SIP", "SWITCH_IN", "SWITCH_OUT"]


def get_categories_for_type(inv_type: str) -> list:
    if inv_type == "MF":
        return MF_CATEGORIES
    elif inv_type == "AIF":
        return AIF_CATEGORIES
    elif inv_type == "PMS":
        return PMS_CATEGORIES
    return ["Other"]


def format_inr(value: float) -> str:
    """Format number as Indian Rupee with lakh/crore notation."""
    if value is None:
        return "—"
    if abs(value) >= 1e7:
        return f"₹{value/1e7:.2f} Cr"
    elif abs(value) >= 1e5:
        return f"₹{value/1e5:.2f} L"
    else:
        return f"₹{value:,.2f}"


def format_xirr(xirr_pct):
    """Format XIRR with color class."""
    if xirr_pct is None:
        return "—"
    return f"{xirr_pct:+.2f}%"


def color_return(value):
    """Return CSS color for positive/negative return."""
    if value is None:
        return "gray"
    return "#2ecc71" if value >= 0 else "#e74c3c"


def compute_xirr_local(cash_flows):
    """
    Local XIRR calculation for instant frontend feedback.
    cash_flows: list of (date: datetime, amount: float)
      - Buy = negative amount
      - Sell/current value = positive amount
    Returns annualized rate as percentage or None.
    """
    if not cash_flows or len(cash_flows) < 2:
        return None
    
    sorted_flows = sorted(cash_flows, key=lambda x: x[0])
    base_date = sorted_flows[0][0]
    amounts = [cf[1] for cf in sorted_flows]
    days = [(cf[0] - base_date).days for cf in sorted_flows]
    
    if not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        return None
    
    def npv(rate):
        return sum(a / ((1 + rate) ** (d / 365.0)) for a, d in zip(amounts, days))
    
    def dnpv(rate):
        return sum(-a * (d / 365.0) / ((1 + rate) ** (d / 365.0 + 1)) for a, d in zip(amounts, days))
    
    rate = 0.1
    for _ in range(500):
        try:
            v = npv(rate)
            dv = dnpv(rate)
            if abs(dv) < 1e-10:
                break
            nr = rate - v / dv
            if abs(nr - rate) < 1e-6:
                return nr * 100
            rate = max(-0.9, nr)
        except Exception:
            break
    
    return None


def parse_date(date_str):
    """Parse date from various formats."""
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y']:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return None


def sidebar_filters(investments):
    """Render sidebar filter widgets and return filtered list."""
    with st.sidebar:
        st.markdown("### Filters")
        
        inv_types = ["All"] + sorted(set(i.get('investment_type', 'MF') for i in investments))
        selected_type = st.selectbox("Investment Type", inv_types)
        
        categories = ["All"] + sorted(set(i.get('category', '') for i in investments if i.get('category')))
        selected_cat = st.selectbox("Category", categories)
        
        show_inactive = st.checkbox("Show Inactive", value=False)
    
    filtered = investments
    if selected_type != "All":
        filtered = [i for i in filtered if i.get('investment_type') == selected_type]
    if selected_cat != "All":
        filtered = [i for i in filtered if i.get('category') == selected_cat]
    if not show_inactive:
        filtered = [i for i in filtered if i.get('is_active', True)]
    
    return filtered, selected_type, selected_cat
