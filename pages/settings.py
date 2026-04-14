"""
Settings Page — Manage digest email list, user preferences.
"""
import streamlit as st
import hashlib
from utils.api import APIClient


def render():
    st.markdown("## ⚙️ Settings")
    
    tab_account, tab_digest, tab_nav = st.tabs(["👤 Account", "📧 Weekly Digest", "🔄 NAV Settings"])
    
    with tab_account:
        st.markdown("#### Change Password")
        st.caption("Passwords are hashed. Update `secrets.toml` with the new hash.")
        
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pass")
        
        if st.button("Generate Password Hash", key="gen_hash"):
            if not new_password:
                st.warning("Enter a password")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                hashed = hashlib.sha256(new_password.encode()).hexdigest()
                st.success("Password hash generated! Copy this into your secrets.toml:")
                st.code(f'[users]\n{st.session_state.get("username", "your_username")} = "{hashed}"')
                st.warning("⚠️ Update this in Streamlit Community Cloud secrets, not in the source code.")
        
        st.divider()
        st.markdown("#### Session Info")
        st.markdown(f"**Username:** {st.session_state.get('username', '—')}")
        st.markdown(f"**User ID:** {st.session_state.get('user_id', '—')}")
    
    with tab_digest:
        st.markdown("#### Weekly Digest Configuration")
        st.caption("The weekly digest is sent every Monday morning. Configure recipients in AWS.")
        
        st.info("""
        Email recipients are configured in the **AWS CloudFormation stack** parameter `AlertEmails`.
        
        To update recipients:
        1. Go to AWS CloudFormation console
        2. Select your `mf-tracker-prod` stack
        3. Click **Update** → **Use current template**
        4. Update the `AlertEmails` parameter (comma-separated emails)
        5. Deploy the change
        
        The SES sender email must be verified in AWS SES.
        """)
        
        st.markdown("#### Manual Digest Trigger")
        st.caption("Send a digest email right now (useful for testing).")
        if st.button("📧 Send Digest Now", type="secondary", key="send_digest_now"):
            st.info("Trigger the `mf-weekly-digest` Lambda manually from the AWS console, or invoke it via CLI:\n\n`aws lambda invoke --function-name mf-weekly-digest-prod /tmp/out.json`")
    
    with tab_nav:
        st.markdown("#### NAV Fetch Schedule")
        st.info("""
        **Mutual Funds (AMFI):** NAVs are automatically fetched **Monday–Friday at ~10 PM IST** via EventBridge schedule.
        
        **AIF / PMS / Complex Debt:** These instruments don't have public NAV APIs. Use the **Manual NAV Entry** feature in the Investments page to update values.
        
        To manually trigger a NAV fetch:
        ```bash
        aws lambda invoke \\
          --function-name mf-nav-fetcher-prod \\
          /tmp/nav_response.json
        ```
        """)
        
        st.markdown("#### About XIRR Calculation")
        st.markdown("""
        - **Formula:** Newton-Raphson XIRR (same as Excel XIRR function)
        - **Convention:** Cash outflows (investments) = negative, inflows (redemptions + current value) = positive
        - **Current value terminal date:** Today's date
        - **MF Current Value:** Units held × Latest AMFI NAV
        - **AIF/PMS Current Value:** Last manually entered value
        - **XIRR is annualized** — it represents the equivalent annual return
        """)
