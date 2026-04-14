"""
Import / Export Page — Bulk CSV upload for investments/transactions, and CSV export.
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime
from utils.api import APIClient
from utils.helpers import INVESTMENT_TYPES, get_categories_for_type, TXN_TYPES


# ─── CSV Templates ────────────────────────────────────────────────────────────

INVESTMENT_TEMPLATE = pd.DataFrame([{
    'scheme_name': 'HDFC Mid-Cap Opportunities Fund',
    'investment_type': 'MF',
    'category': 'Equity - Mid Cap',
    'amc': 'HDFC AMC',
    'scheme_code': '118560',
    'notes': ''
}, {
    'scheme_name': 'ABC AIF Category II',
    'investment_type': 'AIF',
    'category': 'Category II - Private Equity',
    'amc': 'ABC Asset Management',
    'scheme_code': '',
    'notes': 'Minimum lock-in 3 years'
}])

TRANSACTION_TEMPLATE = pd.DataFrame([{
    'scheme_name': 'HDFC Mid-Cap Opportunities Fund',
    'txn_date': '2024-01-15',
    'txn_type': 'BUY',
    'amount': 50000,
    'units': 312.5,
    'nav_at_txn': 160.0,
    'notes': 'Lumpsum'
}, {
    'scheme_name': 'HDFC Mid-Cap Opportunities Fund',
    'txn_date': '2024-02-01',
    'txn_type': 'SIP',
    'amount': 5000,
    'units': 29.8,
    'nav_at_txn': 167.79,
    'notes': 'Monthly SIP'
}])


def render():
    st.markdown("## 📤 Import / Export")
    
    tab_export, tab_import_inv, tab_import_txn = st.tabs([
        "⬇️ Export Data", "📥 Import Investments", "📥 Import Transactions"
    ])
    
    # ─── Tab 1: Export ────────────────────────────────────────────────────
    with tab_export:
        st.markdown("#### Export Portfolio Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Export Investments**")
            if st.button("📊 Download Investments CSV", key="export_inv"):
                with st.spinner("Fetching..."):
                    resp = APIClient.get_investments()
                investments = resp.get('investments', []) if resp else []
                
                if investments:
                    df = pd.DataFrame([{
                        'investment_id': i['investment_id'],
                        'scheme_name': i['scheme_name'],
                        'investment_type': i.get('investment_type', ''),
                        'category': i.get('category', ''),
                        'amc': i.get('amc', ''),
                        'scheme_code': i.get('scheme_code', ''),
                        'latest_nav': i.get('latest_nav', ''),
                        'latest_nav_date': i.get('latest_nav_date', ''),
                        'manual_current_value': i.get('manual_current_value', ''),
                        'is_active': i.get('is_active', True),
                        'notes': i.get('notes', ''),
                        'created_at': i.get('created_at', '')
                    } for i in investments])
                    
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Click to Download",
                        data=csv,
                        file_name=f"investments_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="dl_inv"
                    )
                else:
                    st.info("No investments to export.")
        
        with col2:
            st.markdown("**Export Transactions**")
            
            resp_inv = APIClient.get_investments()
            investments_all = resp_inv.get('investments', []) if resp_inv else []
            
            if st.button("📊 Download All Transactions CSV", key="export_txn"):
                all_txns = []
                for inv in investments_all:
                    txn_resp = APIClient.get_transactions(inv['investment_id'])
                    txns = txn_resp.get('transactions', []) if txn_resp else []
                    for t in txns:
                        all_txns.append({
                            'scheme_name': inv['scheme_name'],
                            'investment_type': inv.get('investment_type', ''),
                            'investment_id': t['investment_id'],
                            'txn_id': t['txn_id'],
                            'txn_date': t['txn_date'],
                            'txn_type': t['txn_type'],
                            'amount': float(t['amount']),
                            'units': float(t.get('units', 0)),
                            'nav_at_txn': float(t.get('nav_at_txn', 0)),
                            'notes': t.get('notes', '')
                        })
                
                if all_txns:
                    df = pd.DataFrame(all_txns)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Click to Download",
                        data=csv,
                        file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="dl_txn"
                    )
                else:
                    st.info("No transactions to export.")
        
        st.divider()
        st.markdown("**Download CSV Templates**")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.download_button(
                "📄 Investments Template",
                data=INVESTMENT_TEMPLATE.to_csv(index=False),
                file_name="investments_template.csv",
                mime="text/csv",
                key="tmpl_inv"
            )
        with col_t2:
            st.download_button(
                "📄 Transactions Template",
                data=TRANSACTION_TEMPLATE.to_csv(index=False),
                file_name="transactions_template.csv",
                mime="text/csv",
                key="tmpl_txn"
            )
    
    # ─── Tab 2: Import Investments ────────────────────────────────────────
    with tab_import_inv:
        st.markdown("#### Bulk Import Investments")
        st.caption("Upload a CSV with columns: `scheme_name`, `investment_type`, `category`, `amc`, `scheme_code`, `notes`")
        
        uploaded = st.file_uploader("Choose CSV file", type="csv", key="upload_inv")
        
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                required = ['scheme_name', 'investment_type']
                missing = [c for c in required if c not in df.columns]
                
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    st.markdown(f"**Preview** — {len(df)} rows found:")
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Validate
                    invalid_types = df[~df['investment_type'].isin(INVESTMENT_TYPES)]
                    if not invalid_types.empty:
                        st.warning(f"⚠️ {len(invalid_types)} rows have invalid investment_type. Valid: {INVESTMENT_TYPES}")
                    
                    if st.button("✅ Import All Investments", type="primary", key="do_import_inv"):
                        success = 0
                        errors = 0
                        progress = st.progress(0)
                        
                        for idx, row in df.iterrows():
                            try:
                                result = APIClient.create_investment({
                                    "scheme_name": str(row.get('scheme_name', '')).strip(),
                                    "investment_type": str(row.get('investment_type', 'MF')).strip(),
                                    "category": str(row.get('category', '')).strip(),
                                    "amc": str(row.get('amc', '')).strip(),
                                    "scheme_code": str(row.get('scheme_code', '')).strip(),
                                    "notes": str(row.get('notes', '')).strip()
                                })
                                if result:
                                    success += 1
                                else:
                                    errors += 1
                            except Exception as e:
                                errors += 1
                            
                            progress.progress((idx + 1) / len(df))
                        
                        st.success(f"✅ Imported {success} investments. {errors} errors.")
            
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
    
    # ─── Tab 3: Import Transactions ───────────────────────────────────────
    with tab_import_txn:
        st.markdown("#### Bulk Import Transactions")
        st.caption("Upload a CSV with columns: `scheme_name`, `txn_date` (YYYY-MM-DD), `txn_type`, `amount`, `units`, `nav_at_txn`, `notes`")
        
        uploaded_txn = st.file_uploader("Choose CSV file", type="csv", key="upload_txn")
        
        if uploaded_txn:
            try:
                df = pd.read_csv(uploaded_txn)
                required = ['scheme_name', 'txn_date', 'txn_type', 'amount']
                missing = [c for c in required if c not in df.columns]
                
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    st.markdown(f"**Preview** — {len(df)} rows found:")
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Load investments to map scheme_name → investment_id
                    resp_inv = APIClient.get_investments()
                    inv_name_map = {
                        i['scheme_name']: i['investment_id']
                        for i in (resp_inv.get('investments', []) if resp_inv else [])
                    }
                    
                    unmatched = df[~df['scheme_name'].isin(inv_name_map)]['scheme_name'].unique()
                    if len(unmatched) > 0:
                        st.warning(f"⚠️ These schemes not found in investments (add them first): {', '.join(unmatched[:5])}")
                    
                    if st.button("✅ Import All Transactions", type="primary", key="do_import_txn"):
                        success = 0
                        errors = 0
                        progress = st.progress(0)
                        
                        for idx, row in df.iterrows():
                            scheme = str(row.get('scheme_name', '')).strip()
                            inv_id = inv_name_map.get(scheme)
                            
                            if not inv_id:
                                errors += 1
                                continue
                            
                            try:
                                result = APIClient.add_transaction({
                                    "investment_id": inv_id,
                                    "txn_date": str(row.get('txn_date', '')).strip(),
                                    "txn_type": str(row.get('txn_type', 'BUY')).strip().upper(),
                                    "amount": float(row.get('amount', 0)),
                                    "units": float(row.get('units', 0)) if pd.notna(row.get('units')) else 0,
                                    "nav_at_txn": float(row.get('nav_at_txn', 0)) if pd.notna(row.get('nav_at_txn')) else 0,
                                    "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else ''
                                })
                                if result:
                                    success += 1
                                else:
                                    errors += 1
                            except Exception as e:
                                print(f"Error on row {idx}: {e}")
                                errors += 1
                            
                            progress.progress((idx + 1) / len(df))
                        
                        st.success(f"✅ Imported {success} transactions. {errors} errors.")
                        
                        if success > 0:
                            st.info("Triggering XIRR recalculation...")
                            APIClient.calculate_xirr()
            
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
