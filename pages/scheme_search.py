"""
Scheme Search Page — Search AMFI/mfapi.in by name OR scheme code number.
"""
import streamlit as st
import re
from utils.api import APIClient


def render():
    st.markdown("## 🔍 Scheme Search")

    # ── Search box ────────────────────────────────────────────────────────
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Search by fund name OR scheme code number",
            placeholder="e.g.  HDFC Flexi Cap   or   104685   or   101762",
            key="scheme_search_query"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("🔍 Search", type="primary", use_container_width=True)

    # ── Explain the two modes clearly ────────────────────────────────────
    with st.expander("ℹ️ How to search", expanded=False):
        st.markdown("""
**Search by name** — type part of the fund name:
- `HDFC Flexi Cap` → shows all HDFC Flexi Cap variants (Regular, Direct, Growth, IDCW…)
- `ICICI Balanced Advantage` → shows all ICICI BAF variants
- `Parag Parikh` → shows all PPFAS schemes

**Search by scheme code** — type the 6-digit AMFI code directly:
- `104685` → looks up that exact code and shows its name + latest NAV
- `101762` → same

**Where to find your scheme code:** Check your account statement (CAMS / KFintech).
The scheme code is a 6-digit number next to each fund in the PDF.

**Note:** mfapi.in's text search only works with fund names, not codes.
When you type a number, we look up the code directly on mfapi.in.
        """)

    st.divider()

    # ── Execute search ────────────────────────────────────────────────────
    if search_btn:
        q = query.strip() if query else ""
        if len(q) < 2:
            st.warning("Please enter at least 2 characters.")
            return

        is_code_search = bool(re.fullmatch(r'\d+', q))

        with st.spinner(
            f"Looking up scheme code **{q}**..." if is_code_search
            else f"Searching for **{q}**..."
        ):
            result = APIClient.search_scheme(q)

        if not result:
            st.error("Could not reach the search API. Check your API_BASE_URL in secrets.")
            return

        schemes = result.get('results', [])

        if not schemes:
            st.warning(f"No schemes found for `{q}`.")
            if is_code_search:
                st.markdown("""
**Tips for code searches:**
- Make sure the code is exactly correct (check your CAMS/KFintech statement)
- The code must be a valid AMFI scheme code listed on mfapi.in
- Try searching by name instead to find the right code
                """)
            else:
                st.markdown("""
**Tips for name searches:**
- Try fewer words: `HDFC Flexi` instead of `HDFC Flexi Cap Fund Regular Growth`
- Use the fund house name: `ICICI Balanced` instead of `ICICI Prudential Balanced Advantage`
- Check the **Popular Fund Houses** shortcuts below
                """)
            return

        # ── Results table ─────────────────────────────────────────────────
        if is_code_search:
            st.success(f"Found scheme for code **{q}**")
        else:
            st.success(f"Found **{len(schemes)}** scheme(s) for `{q}`")

        for scheme in schemes:
            code      = scheme['scheme_code']
            name      = scheme['scheme_name']
            house     = scheme.get('fund_house', '')
            category  = scheme.get('category', '')
            nav       = scheme.get('latest_nav', '')
            nav_date  = scheme.get('nav_date', '')

            with st.container():
                col_a, col_b, col_c = st.columns([4, 1, 1])

                with col_a:
                    st.markdown(f"**{name}**")
                    meta_parts = []
                    if house:    meta_parts.append(house)
                    if category: meta_parts.append(category)
                    if nav:      meta_parts.append(f"NAV: ₹{nav}  ({nav_date})")
                    if meta_parts:
                        st.caption("  ·  ".join(meta_parts))

                with col_b:
                    st.code(code)

                with col_c:
                    if st.button("➕ Add", key=f"add_{code}",
                                 help="Go to Investments page pre-filled with this scheme"):
                        st.session_state.prefill_scheme = scheme
                        st.session_state.page = "investments"
                        st.rerun()

                st.divider()

    # ── Popular fund houses ───────────────────────────────────────────────
    st.markdown("#### Popular Fund Houses")
    amcs = [
        "SBI", "HDFC", "ICICI Prudential", "Axis", "Mirae Asset",
        "Kotak", "DSP", "Nippon India", "UTI", "Franklin",
        "Aditya Birla", "Tata", "PPFAS", "Edelweiss", "Invesco",
    ]
    cols = st.columns(5)
    for i, amc in enumerate(amcs):
        with cols[i % 5]:
            if st.button(amc, key=f"amc_{i}", use_container_width=True):
                st.session_state.scheme_search_query = amc
                st.rerun()

    st.divider()

    # ── How scheme codes work ─────────────────────────────────────────────
    st.markdown("#### How Scheme Codes Work")
    st.markdown("""
- The **AMFI Scheme Code** is a unique 6-digit number for every MF scheme (e.g. `104685`)
- mfapi.in uses these same codes to serve daily NAV data
- Once you add an investment with a scheme code, NAVs are fetched automatically every evening (Mon–Fri)
- **Regular vs Direct plans have different codes** — make sure you pick the one matching your investment
- ELSS, Index, Debt, Hybrid funds are all covered — any SEBI-registered scheme is on mfapi.in
    """)
