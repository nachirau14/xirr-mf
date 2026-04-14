"""
Transactions Page — View and add transactions for each investment.
"""
import streamlit as st
import pandas as pd
from datetime import date
from utils.api import APIClient
from utils.helpers import TXN_TYPES, format_inr, compute_xirr_local
from datetime import datetime


def render():
    st.markdown("## 📋 Transactions")
    
    # Load investments for selector
    resp = APIClient.get_investments()
    investments = resp.get('investments', []) if resp else []
    
    if not investments:
        st.info("No investments found. Add investments first.")
        return
    
    inv_map = {i['scheme_name']: i for i in investments if i.get('is_active', True)}
    
    # Pre-select from dashboard click
    default_name = None
    if st.session_state.get('selected_investment_id'):
        default_name = st.session_state.get('selected_investment_name')
    
    selected_name = st.selectbox(
        "Select Investment",
        list(inv_map.keys()),
        index=list(inv_map.keys()).index(default_name) if default_name in inv_map else 0,
        key="txn_inv_select"
    )
    selected_inv = inv_map.get(selected_name, {})
    inv_id = selected_inv.get('investment_id', '')
    
    if not inv_id:
        return
    
    tab_view, tab_add, tab_xirr = st.tabs(["📋 Transaction History", "➕ Add Transaction", "📊 XIRR Detail"])
    
    # ─── Tab 1: Transaction history ───────────────────────────────────────
    with tab_view:
        with st.spinner("Loading transactions..."):
            txn_resp = APIClient.get_transactions(inv_id)
        
        txns = txn_resp.get('transactions', []) if txn_resp else []
        
        if not txns:
            st.info("No transactions yet. Add one in the **Add Transaction** tab.")
        else:
            # Summary
            buys = [t for t in txns if t['txn_type'] in ['BUY', 'SIP']]
            sells = [t for t in txns if t['txn_type'] == 'SELL']
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Invested", format_inr(sum(float(t['amount']) for t in buys)))
            with col2:
                st.metric("Total Redeemed", format_inr(sum(float(t['amount']) for t in sells)))
            with col3:
                units_held = sum(float(t.get('units', 0)) for t in buys) - \
                             sum(float(t.get('units', 0)) for t in sells)
                st.metric("Units Held", f"{units_held:,.4f}")
            
            st.divider()
            
            df = pd.DataFrame([{
                'Date': t['txn_date'],
                'Type': t['txn_type'],
                'Amount (₹)': float(t['amount']),
                'Units': float(t.get('units', 0)),
                'NAV at Txn': float(t.get('nav_at_txn', 0)),
                'Notes': t.get('notes', ''),
                'ID': t['txn_id']
            } for t in sorted(txns, key=lambda x: x['txn_date'], reverse=True)])
            
            st.dataframe(
                df.drop(columns=['ID']).style.format({
                    'Amount (₹)': '₹{:,.2f}',
                    'Units': '{:,.4f}',
                    'NAV at Txn': '₹{:,.4f}'
                }),
                use_container_width=True, hide_index=True
            )
            
            # Delete individual transaction
            with st.expander("🗑️ Delete a transaction"):
                del_options = {f"{t['txn_date']} | {t['txn_type']} | ₹{float(t['amount']):,.2f}": t['txn_id'] for t in txns}
                del_sel = st.selectbox("Select transaction to delete", list(del_options.keys()), key="del_txn_sel")
                if st.button("Delete", type="secondary", key="del_txn_btn"):
                    APIClient.delete_transaction(inv_id, del_options[del_sel])
                    st.success("Deleted!")
                    st.rerun()
    
    # ─── Tab 2: Add Transaction ───────────────────────────────────────────
    with tab_add:
        st.markdown("#### Add Transaction")
        
        col_a, col_b = st.columns(2)
        with col_a:
            txn_type = st.selectbox("Transaction Type *", TXN_TYPES, key="add_txn_type")
            txn_date = st.date_input("Date *", value=date.today(), key="add_txn_date")
        with col_b:
            amount = st.number_input("Amount (₹) *", min_value=0.0, format="%.2f", key="add_txn_amt")
            units = st.number_input("Units", min_value=0.0, format="%.4f", key="add_txn_units",
                                    help="Optional for AIF/PMS. Required for MF.")
        
        nav_at_txn = st.number_input("NAV at Transaction (₹)", min_value=0.0, format="%.4f", key="add_txn_nav")
        notes = st.text_input("Notes", key="add_txn_notes")
        
        if st.button("✅ Add Transaction", type="primary", key="submit_txn"):
            if amount <= 0:
                st.error("Amount must be greater than 0")
            else:
                with st.spinner("Saving..."):
                    result = APIClient.add_transaction({
                        "investment_id": inv_id,
                        "txn_date": txn_date.strftime('%Y-%m-%d'),
                        "txn_type": txn_type,
                        "amount": float(amount),
                        "units": float(units),
                        "nav_at_txn": float(nav_at_txn),
                        "notes": notes
                    })
                if result:
                    st.success(f"✅ Transaction added!")
                    # Trigger XIRR recalc
                    APIClient.calculate_xirr([inv_id])
    
    # ─── Tab 3: XIRR Detail ───────────────────────────────────────────────
    with tab_xirr:
        st.markdown("#### XIRR Analysis")
        
        txn_resp2 = APIClient.get_transactions(inv_id)
        txns2 = txn_resp2.get('transactions', []) if txn_resp2 else []
        
        if not txns2:
            st.info("No transactions to compute XIRR.")
            return
        
        latest_nav = float(selected_inv.get('latest_nav', 0))
        manual_val = float(selected_inv.get('manual_current_value', 0))
        
        # Current value input
        st.markdown("**Current Value Override**")
        col_cv1, col_cv2 = st.columns(2)
        with col_cv1:
            if latest_nav > 0:
                units_held = sum(float(t.get('units', 0)) for t in txns2 if t['txn_type'] in ['BUY', 'SIP']) - \
                             sum(float(t.get('units', 0)) for t in txns2 if t['txn_type'] == 'SELL')
                auto_val = units_held * latest_nav
                st.metric("Auto Current Value", format_inr(auto_val),
                          help=f"{units_held:.4f} units × ₹{latest_nav:,.4f} NAV")
                current_value = auto_val
            else:
                current_value = manual_val
        
        with col_cv2:
            override_val = st.number_input(
                "Override Current Value (₹)",
                min_value=0.0, format="%.2f",
                value=float(current_value),
                key="xirr_current_val"
            )
        
        # Build cash flows
        cash_flows = []
        for t in txns2:
            try:
                d = datetime.strptime(t['txn_date'], '%Y-%m-%d')
                amt = float(t['amount'])
                if t['txn_type'] in ['BUY', 'SIP']:
                    cash_flows.append((d, -amt))
                elif t['txn_type'] == 'SELL':
                    cash_flows.append((d, amt))
            except Exception:
                pass
        
        cash_flows.append((datetime.now(), float(override_val)))
        
        xirr = compute_xirr_local(cash_flows)
        
        total_invested = sum(abs(cf[1]) for cf in cash_flows if cf[1] < 0)
        gain = float(override_val) - total_invested
        gain_pct = (gain / total_invested * 100) if total_invested > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("XIRR", f"{xirr:+.2f}%" if xirr is not None else "—")
        with col2:
            st.metric("Absolute Gain", format_inr(gain))
        with col3:
            st.metric("Absolute Return", f"{gain_pct:+.2f}%")
