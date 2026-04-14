"""
MF/AIF/PMS XIRR Tracker — Main Entry Point
Handles authentication and navigation.
"""
import streamlit as st
import hashlib
import hmac
from utils.api import APIClient

st.set_page_config(
    page_title="Portfolio XIRR Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main-title { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        border-left: 4px solid #0f3460;
    }
    .positive { color: #2ecc71; font-weight: 600; }
    .negative { color: #e74c3c; font-weight: 600; }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    div[data-testid="stMetric"] {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)


# ─── Auth ─────────────────────────────────────────────────────────────────────

def check_password():
    """Hashed password check using HMAC. Passwords stored in st.secrets."""
    
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    if "authenticated" in st.session_state and st.session_state.authenticated:
        return True
    
    st.markdown('<p class="main-title">📊 Portfolio XIRR Tracker</p>', unsafe_allow_html=True)
    st.markdown("##### Sign in to access your portfolio")
    st.divider()
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("**Username**")
            username = st.text_input("Username", placeholder="Enter username", label_visibility="collapsed")
            st.markdown("**Password**")
            password = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
        
        if submitted:
            users = st.secrets.get("users", {})
            if username in users:
                stored_hash = users[username]
                if hmac.compare_digest(hash_password(password), stored_hash):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_id = users.get(f"{username}_id", username)
                    st.rerun()
                else:
                    st.error("Incorrect password")
            else:
                st.error("User not found")
    
    return False


# ─── Sidebar Navigation ───────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 📊 MF Tracker")
        st.caption(f"Logged in as **{st.session_state.get('username', '')}**")
        st.divider()
        
        pages = {
            "🏠 Dashboard": "dashboard",
            "💼 Investments": "investments",
            "📋 Transactions": "transactions",
            "📈 Analytics": "analytics",
            "🔍 Scheme Search": "scheme_search",
            "📤 Import / Export": "import_export",
            "⚙️ Settings": "settings",
        }
        
        current = st.session_state.get("page", "dashboard")
        for label, page_id in pages.items():
            is_active = current == page_id
            if st.button(label, use_container_width=True,
                         type="primary" if is_active else "secondary",
                         key=f"nav_{page_id}"):
                st.session_state.page = page_id
                st.rerun()
        
        st.divider()
        if st.button("🔒 Sign Out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not check_password():
        return
    
    render_sidebar()
    
    page = st.session_state.get("page", "dashboard")
    
    if page == "dashboard":
        from pages.dashboard import render
        render()
    elif page == "investments":
        from pages.investments import render
        render()
    elif page == "transactions":
        from pages.transactions import render
        render()
    elif page == "analytics":
        from pages.analytics import render
        render()
    elif page == "scheme_search":
        from pages.scheme_search import render
        render()
    elif page == "import_export":
        from pages.import_export import render
        render()
    elif page == "settings":
        from pages.settings import render
        render()


if __name__ == "__main__":
    main()
