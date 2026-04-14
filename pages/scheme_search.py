"""
Scheme Search Page — Search AMFI for MF scheme codes.
"""
import streamlit as st
from utils.api import APIClient
from utils.helpers import get_categories_for_type


def render():
    st.markdown("## 🔍 Scheme Search")
    st.caption(
        "Search all SEBI-registered mutual funds via **mfapi.in** (free, no key needed). "
        "Scheme codes from here are used for automatic daily NAV fetch. "
        "AIF and PMS are not listed here — add them manually and use Manual NAV Entry."
    )

    # --- FIX START: Check if an AMC was selected from a previous interaction ---
    if "selected_amc" in st.session_state:
        st.session_state.scheme_search_query = st.session_state.pop("selected_amc")
    # --- FIX END ---

    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Search fund name",
            placeholder="e.g. HDFC Mid Cap, Mirae Large Cap, Parag Parikh...",
            key="scheme_search_query"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("🔍 Search", type="primary", use_container_width=True)

    if search_btn and query and len(query.strip()) >= 2:
        with st.spinner("Searching via mfapi.in..."):
            result = APIClient.search_scheme(query.strip())

        if result and result.get('results'):
            schemes = result['results']
            st.success(f"Found {len(schemes)} schemes")

            for scheme in schemes:
                col_a, col_b, col_c = st.columns([3, 1, 1])
                with col_a:
                    st.markdown(f"**{scheme['scheme_name']}**")
                with col_b:
                    st.code(scheme['scheme_code'])
                with col_c:
                    if st.button("➕ Quick Add", key=f"add_{scheme['scheme_code']}"):
                        st.session_state.prefill_scheme = scheme
                        st.session_state.page = "investments"
                        st.rerun()
                st.divider()
        else:
            st.warning("No schemes found. Try a different search term.")

    elif search_btn:
        st.warning("Please enter at least 2 characters to search.")

    st.divider()

    st.markdown("#### How Scheme Codes Work")
    st.markdown("""
    - The **Scheme Code** is the AMFI code (e.g. `119551`, `125497`)
    - mfapi.in uses the same codes — copy the code and paste it in **Add Investment**
    - Once added, NAVs are fetched automatically every evening (Mon–Fri)
    - To see the full NAV history for any fund, invoke the fetcher with `force_full_refresh: true`
    """)

    st.divider()
    st.markdown("#### Popular Fund Houses")
    amcs = [
        "SBI", "HDFC", "ICICI Prudential", "Axis", "Mirae Asset",
        "Kotak", "DSP", "Nippon India", "UTI", "Franklin",
        "Aditya Birla", "Tata", "PPFAS", "Edelweiss", "Invesco"
    ]
    cols = st.columns(5)
    for i, amc in enumerate(amcs):
        with cols[i % 5]:
            # FIX: We set a temporary key instead of modifying the locked widget key
            if st.button(amc, key=f"quick_amc_{i}", use_container_width=True):
                st.session_state.selected_amc = amc
                st.rerun()
