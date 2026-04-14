"""
Investments Page — Add, view, update, delete investment records.
"""
import streamlit as st
import pandas as pd
from utils.api import APIClient
from utils.helpers import (
    INVESTMENT_TYPES, get_categories_for_type, format_inr, format_xirr
)


def render():
    st.markdown("## 💼 Investments")
    
    tab_list, tab_add, tab_manual_nav = st.tabs(["📋 All Investments", "➕ Add Investment", "📝 Manual NAV Entry"])
    
    # ─── Tab 1: List investments ──────────────────────────────────────────
    with tab_list:
        col_filter, col_refresh = st.columns([5, 1])
        
        with col_filter:
            filter_type = st.selectbox("Filter by Type", ["All"] + INVESTMENT_TYPES, key="inv_filter_type")
        with col_refresh:
            st.markdown("<br>", unsafe_allow_html=True)
            refresh = st.button("🔄", help="Refresh", key="inv_refresh")
        
        params = {}
        if filter_type != "All":
            params["inv_type"] = filter_type
        
        with st.spinner("Loading..."):
            resp = APIClient.get_investments(inv_type=filter_type if filter_type != "All" else None)
        
        if resp and resp.get('investments'):
            investments = resp['investments']
            
            for inv in investments:
                with st.expander(
                    f"{'🟢' if inv.get('is_active', True) else '🔴'} {inv['scheme_name']} "
                    f"— {inv.get('investment_type', 'MF')} / {inv.get('category', '')}",
                    expanded=False
                ):
                    col_info, col_nav, col_actions = st.columns([3, 2, 1])
                    
                    with col_info:
                        st.markdown(f"**AMC:** {inv.get('amc', '—')}")
                        st.markdown(f"**Scheme Code:** {inv.get('scheme_code', '—')}")
                        st.markdown(f"**Notes:** {inv.get('notes', '—')}")
                    
                    with col_nav:
                        nav = inv.get('latest_nav')
                        nav_date = inv.get('latest_nav_date', '')
                        st.markdown(f"**Latest NAV:** {f'₹{float(nav):,.4f}' if nav else '—'}")
                        st.markdown(f"**NAV Date:** {nav_date or '—'}")
                        manual_val = inv.get('manual_current_value')
                        if manual_val:
                            st.markdown(f"**Manual Value:** {format_inr(float(manual_val))}")
                    
                    with col_actions:
                        inv_id = inv['investment_id']
                        
                        # Toggle active
                        is_active = inv.get('is_active', True)
                        if st.button("Deactivate" if is_active else "Activate", key=f"toggle_{inv_id}"):
                            APIClient.update_investment(inv_id, {"is_active": not is_active})
                            st.rerun()
                        
                        # View transactions
                        if st.button("Transactions →", key=f"txn_{inv_id}"):
                            st.session_state.page = "transactions"
                            st.session_state.selected_investment_id = inv_id
                            st.session_state.selected_investment_name = inv['scheme_name']
                            st.rerun()
                        
                        # Calculate XIRR
                        if st.button("Calc XIRR", key=f"xirr_{inv_id}"):
                            with st.spinner("Calculating..."):
                                APIClient.calculate_xirr([inv_id])
                            st.success("Done!")
        else:
            st.info("No investments found. Add one in the **Add Investment** tab.")
    
    # ─── Tab 2: Add Investment ────────────────────────────────────────────
    with tab_add:
        st.markdown("#### Add New Investment")
        
        col_a, col_b = st.columns(2)
        with col_a:
            inv_type = st.selectbox("Investment Type *", INVESTMENT_TYPES, key="add_inv_type")
        with col_b:
            categories = get_categories_for_type(inv_type)
            category = st.selectbox("Category *", categories, key="add_inv_cat")
        
        scheme_name = st.text_input("Scheme / Fund Name *", key="add_scheme_name")
        
        col_c, col_d = st.columns(2)
        with col_c:
            amc = st.text_input("AMC / Manager", key="add_amc")
        with col_d:
            scheme_code = st.text_input(
                "AMFI Scheme Code (for MF auto-NAV fetch)",
                key="add_scheme_code",
                help="Leave blank for AIF/PMS. Find using Scheme Search page."
            )
        
        notes = st.text_area("Notes", key="add_notes")
        
        if st.button("✅ Add Investment", type="primary", key="submit_inv"):
            if not scheme_name.strip():
                st.error("Scheme name is required")
            else:
                with st.spinner("Adding..."):
                    result = APIClient.create_investment({
                        "scheme_name": scheme_name.strip(),
                        "investment_type": inv_type,
                        "category": category,
                        "amc": amc.strip(),
                        "scheme_code": scheme_code.strip(),
                        "notes": notes.strip()
                    })
                if result:
                    st.success(f"✅ **{scheme_name}** added successfully!")
                    st.balloons()
    
    # ─── Tab 3: Manual NAV Entry (AIF/PMS/Complex debt) ──────────────────
    with tab_manual_nav:
        st.markdown("#### Manual NAV / Value Entry")
        st.caption("Use this for AIF, PMS, complex debt funds, or any instrument without automatic NAV fetch.")
        
        # Load investments to select from
        resp = APIClient.get_investments()
        investments_all = resp.get('investments', []) if resp else []
        
        # Show AIF/PMS prominently, but allow any
        eligible = [i for i in investments_all if i.get('investment_type') in ['AIF', 'PMS'] or True]
        
        if not eligible:
            st.info("No investments found. Add one first.")
        else:
            inv_options = {i['scheme_name']: i['investment_id'] for i in eligible}
            selected_name = st.selectbox("Select Investment", list(inv_options.keys()), key="manual_nav_inv")
            selected_id = inv_options.get(selected_name)
            
            col_x, col_y = st.columns(2)
            with col_x:
                nav_date = st.date_input("Date", key="manual_nav_date")
                nav_value = st.number_input("NAV per unit (₹)", min_value=0.0, format="%.4f", key="manual_nav_val")
            with col_y:
                total_value = st.number_input(
                    "Total Portfolio Value (₹) — optional",
                    min_value=0.0, format="%.2f", key="manual_total_val",
                    help="If you know the total value directly, enter it here. Otherwise leave 0."
                )
            
            if st.button("📝 Save NAV", type="primary", key="save_manual_nav"):
                with st.spinner("Saving..."):
                    result = APIClient.add_manual_nav(
                        investment_id=selected_id,
                        nav_date=nav_date.strftime('%Y-%m-%d'),
                        nav_value=float(nav_value),
                        total_value=float(total_value) if total_value > 0 else None
                    )
                if result:
                    st.success("✅ NAV saved successfully!")
