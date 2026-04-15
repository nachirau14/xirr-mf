"""
Investments Page — Add, view, update, delete investment records.
Includes Scheme Code Fixer tab for correcting wrong/missing scheme codes.
"""
import streamlit as st
import pandas as pd
from utils.api import APIClient
from utils.helpers import (
    INVESTMENT_TYPES, get_categories_for_type, format_inr
)


def render():
    st.markdown("## 💼 Investments")

    tab_list, tab_add, tab_fix, tab_manual_nav = st.tabs([
        "📋 All Investments",
        "➕ Add Investment",
        "🔧 Fix Scheme Code / NAV",
        "📝 Manual NAV Entry",
    ])

    # ─── Tab 1: List investments ──────────────────────────────────────────
    with tab_list:
        col_filter, col_refresh = st.columns([5, 1])
        with col_filter:
            filter_type = st.selectbox("Filter by Type", ["All"] + INVESTMENT_TYPES,
                                       key="inv_filter_type")
        with col_refresh:
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("🔄", help="Refresh", key="inv_refresh")

        with st.spinner("Loading..."):
            resp = APIClient.get_investments(
                inv_type=filter_type if filter_type != "All" else None
            )

        if resp and resp.get('investments'):
            investments = resp['investments']
            st.caption(f"{len(investments)} investment(s)")

            for inv in investments:
                inv_id   = inv['investment_id']
                is_active = inv.get('is_active', True)
                latest_nav  = inv.get('latest_nav')
                nav_date    = inv.get('latest_nav_date', '')
                scheme_code = inv.get('scheme_code', '')

                # Flag stale / missing NAVs visually
                nav_ok = _nav_is_fresh(latest_nav, nav_date)
                nav_icon = "✅" if nav_ok else ("⚠️" if latest_nav else "❌")

                label = (
                    f"{'🟢' if is_active else '🔴'} "
                    f"{inv['scheme_name']} "
                    f"— {inv.get('investment_type','MF')} / {inv.get('category','')}  "
                    f"{nav_icon} NAV: {'₹{:.4f}'.format(float(latest_nav)) if latest_nav else 'None'}  "
                    f"Code: {scheme_code or '—'}"
                )

                with st.expander(label, expanded=False):
                    col_info, col_nav, col_actions = st.columns([3, 2, 1])

                    with col_info:
                        st.markdown(f"**AMC:** {inv.get('amc','—')}")
                        st.markdown(f"**Scheme Code:** `{scheme_code or '—'}`")
                        st.markdown(f"**Notes:** {inv.get('notes','—')}")

                    with col_nav:
                        st.markdown(f"**Latest NAV:** {'₹{:.4f}'.format(float(latest_nav)) if latest_nav else '—'}")
                        st.markdown(f"**NAV Date:** {nav_date or '—'}")
                        if not nav_ok:
                            if not latest_nav:
                                st.error("No NAV — add scheme code and trigger fetch")
                            else:
                                st.warning("NAV looks stale — check scheme code")
                        manual_val = inv.get('manual_current_value')
                        if manual_val:
                            st.markdown(f"**Manual Value:** {format_inr(float(manual_val))}")

                    with col_actions:
                        if st.button("Deactivate" if is_active else "Activate",
                                     key=f"toggle_{inv_id}"):
                            APIClient.update_investment(inv_id, {"is_active": not is_active})
                            st.rerun()

                        if st.button("Transactions →", key=f"txn_{inv_id}"):
                            st.session_state.page = "transactions"
                            st.session_state.selected_investment_id = inv_id
                            st.session_state.selected_investment_name = inv['scheme_name']
                            st.rerun()

                        if st.button("Calc XIRR", key=f"xirr_{inv_id}"):
                            with st.spinner("Calculating..."):
                                APIClient.calculate_xirr([inv_id])
                            st.success("Done!")
        else:
            st.info("No investments found. Add one in the **Add Investment** tab.")

    # ─── Tab 2: Add Investment ────────────────────────────────────────────
    with tab_add:
        st.markdown("#### Add New Investment")
        st.caption("Tip: Use **Scheme Search** page to look up the AMFI scheme code first.")

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
                "AMFI Scheme Code",
                key="add_scheme_code",
                help="Required for MF auto-NAV. Find via Scheme Search page."
            )

        notes = st.text_area("Notes", key="add_notes")

        if st.button("✅ Add Investment", type="primary", key="submit_inv"):
            if not scheme_name.strip():
                st.error("Scheme name is required")
            else:
                with st.spinner("Adding..."):
                    result = APIClient.create_investment({
                        "scheme_name":    scheme_name.strip(),
                        "investment_type": inv_type,
                        "category":       category,
                        "amc":            amc.strip(),
                        "scheme_code":    scheme_code.strip(),
                        "notes":          notes.strip(),
                    })
                if result:
                    st.success(f"✅ **{scheme_name}** added!")
                    st.info("Now add transactions in the Transactions page, "
                            "then trigger a NAV fetch to get current values.")

    # ─── Tab 3: Fix Scheme Code / NAV ────────────────────────────────────
    with tab_fix:
        _render_fix_tab()

    # ─── Tab 4: Manual NAV Entry ──────────────────────────────────────────
    with tab_manual_nav:
        st.markdown("#### Manual NAV / Value Entry")
        st.caption("For AIF, PMS, complex debt, or any instrument without automatic NAV.")

        resp2 = APIClient.get_investments()
        investments_all = resp2.get('investments', []) if resp2 else []

        if not investments_all:
            st.info("No investments found.")
        else:
            inv_options = {i['scheme_name']: i['investment_id'] for i in investments_all}
            selected_name = st.selectbox("Select Investment", list(inv_options.keys()),
                                         key="manual_nav_inv")
            selected_id = inv_options.get(selected_name)

            col_x, col_y = st.columns(2)
            with col_x:
                nav_date = st.date_input("Date", key="manual_nav_date")
                nav_value = st.number_input("NAV per unit (₹)", min_value=0.0,
                                            format="%.4f", key="manual_nav_val")
            with col_y:
                total_value = st.number_input(
                    "Total Portfolio Value (₹) — optional",
                    min_value=0.0, format="%.2f", key="manual_total_val",
                    help="If you know total value directly, enter here."
                )

            if st.button("📝 Save NAV", type="primary", key="save_manual_nav"):
                with st.spinner("Saving..."):
                    result = APIClient.add_manual_nav(
                        investment_id=selected_id,
                        nav_date=nav_date.strftime('%Y-%m-%d'),
                        nav_value=float(nav_value),
                        total_value=float(total_value) if total_value > 0 else None,
                    )
                if result:
                    st.success("✅ NAV saved!")


# ─── Scheme Code Fixer ────────────────────────────────────────────────────────

def _render_fix_tab():
    """
    Lets the user search for the correct AMFI scheme code, preview the current
    NAV from mfapi.in, and update the investment record in one click.
    Also triggers a fresh NAV fetch and XIRR recalculation.
    """
    st.markdown("#### 🔧 Fix Scheme Code & Force NAV Refresh")
    st.markdown("""
Use this when:
- XIRR shows wrong current value (stale NAV like ₹10 from inception)
- Current Value shows ₹0
- NAV date is very old
- You added an investment without a scheme code

**Step 1:** Select the investment to fix.  
**Step 2:** Search for the correct scheme code.  
**Step 3:** Apply — this updates the code, fetches fresh NAV, and recalculates XIRR.
    """)

    resp = APIClient.get_investments()
    investments = resp.get('investments', []) if resp else []
    if not investments:
        st.info("No investments to fix.")
        return

    inv_options = {
        f"{i['scheme_name']} (code: {i.get('scheme_code','none')})": i
        for i in investments
    }
    selected_label = st.selectbox("Select investment to fix",
                                  list(inv_options.keys()), key="fix_inv_sel")
    selected_inv = inv_options[selected_label]
    inv_id = selected_inv['investment_id']

    st.divider()

    # Show current state
    col_cur, col_new = st.columns(2)
    with col_cur:
        st.markdown("**Current state**")
        st.markdown(f"Name: `{selected_inv['scheme_name']}`")
        st.markdown(f"Scheme code: `{selected_inv.get('scheme_code','—')}`")
        nav = selected_inv.get('latest_nav')
        nav_date = selected_inv.get('latest_nav_date','—')
        st.markdown(f"Latest NAV: `{'₹{:.4f}'.format(float(nav)) if nav else 'None'}`")
        st.markdown(f"NAV date: `{nav_date}`")
        if nav and nav_date:
            nav_ok = _nav_is_fresh(nav, nav_date)
            if not nav_ok:
                st.error("⚠️ NAV is stale or wrong — fix the scheme code below")
            else:
                st.success("NAV looks fresh")

    with col_new:
        st.markdown("**Search for correct scheme code**")
        search_q = st.text_input("Type fund name to search AMFI",
                                 value=selected_inv['scheme_name'][:30],
                                 key="fix_search_q")
        search_btn = st.button("🔍 Search mfapi.in", key="fix_search_btn")

    if search_btn and search_q:
        with st.spinner("Searching..."):
            result = APIClient.search_scheme(search_q.strip())

        schemes = result.get('results', []) if result else []
        if not schemes:
            st.warning("No results — try a shorter or different search term")
        else:
            st.markdown(f"**{len(schemes)} results:**")

            # Store selected scheme in session state
            scheme_labels = {
                f"{s['scheme_code']} — {s['scheme_name']}": s
                for s in schemes
            }
            chosen_label = st.selectbox("Select the correct scheme",
                                        list(scheme_labels.keys()),
                                        key="fix_scheme_sel")
            chosen = scheme_labels[chosen_label]

            st.info(f"Selected: **{chosen['scheme_name']}** (code `{chosen['scheme_code']}`)")

            st.divider()
            st.markdown("**Confirm and apply**")
            col_b1, col_b2 = st.columns(2)

            with col_b1:
                if st.button("✅ Update Code Only", key="fix_code_only",
                             help="Updates scheme code without fetching NAV yet"):
                    with st.spinner("Updating..."):
                        APIClient.update_investment(inv_id, {
                            "scheme_code": chosen['scheme_code'],
                        })
                    st.success(f"Scheme code updated to `{chosen['scheme_code']}`")
                    st.info("Now click **Update Code + Fetch NAV + Recalculate** to get current values.")

            with col_b2:
                if st.button("🚀 Update Code + Fetch NAV + Recalculate XIRR",
                             type="primary", key="fix_full",
                             help="Updates code, fetches latest NAV from mfapi.in, recalculates XIRR"):
                    progress = st.progress(0, "Updating scheme code...")

                    # 1. Update scheme code
                    APIClient.update_investment(inv_id, {
                        "scheme_code": chosen['scheme_code'],
                    })
                    progress.progress(25, "Fetching NAV from mfapi.in...")

                    # 2. Trigger NAV fetch for this scheme only
                    result2 = APIClient.calculate_xirr.__func__ if False else None
                    nav_result = _trigger_nav_fetch(chosen['scheme_code'])
                    progress.progress(60, "Recalculating XIRR...")

                    # 3. Trigger XIRR recalculation
                    APIClient.calculate_xirr([inv_id])
                    progress.progress(100, "Done!")

                    st.success(
                        f"✅ Done! Scheme code set to `{chosen['scheme_code']}`, "
                        f"NAV fetch triggered, XIRR recalculated."
                    )
                    st.info("Refresh the Dashboard to see updated values.")

    st.divider()
    st.markdown("#### 🔄 Force NAV Fetch for All Investments")
    st.caption("Triggers the NAV fetcher Lambda immediately for all MF scheme codes in your portfolio.")
    if st.button("⚡ Fetch Latest NAVs Now", key="force_nav_all"):
        with st.spinner("Triggering NAV fetch..."):
            result = APIClient.trigger_nav_fetch()
        if result:
            st.success("NAV fetch triggered! Check back in ~30 seconds and refresh the dashboard.")
        else:
            st.error("Could not trigger NAV fetch. Check AWS Lambda logs.")

    st.divider()
    st.markdown("#### 🧮 Recalculate All XIRRs")
    if st.button("🔁 Recalculate All XIRRs", key="recalc_all"):
        with st.spinner("Recalculating..."):
            APIClient.calculate_xirr()
        st.success("XIRR recalculation triggered for all investments.")


def _nav_is_fresh(nav, nav_date_str):
    """Return True if NAV date is within last 10 days."""
    if not nav or not nav_date_str or nav_date_str == '—':
        return False
    from datetime import datetime
    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d-%b-%Y', '%d/%m/%Y'):
        try:
            nav_dt = datetime.strptime(nav_date_str.strip(), fmt)
            return (datetime.now() - nav_dt).days <= 10
        except ValueError:
            pass
    return False


def _trigger_nav_fetch(scheme_code: str):
    """Call the API to trigger a NAV fetch for a specific scheme code."""
    from utils.api import api_call
    return api_call("POST", "/nav-fetch",
                    json_body={"scheme_codes": [scheme_code]},
                    silent=True)
