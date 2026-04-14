"""
Import / Export Page
Handles:
  - Our own CSV template (investments + transactions)
  - CAMS CAS CSV export (via casparser or cams2csv tool)
  - KFintech CAS CSV export
  - Export to CSV
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from utils.api import APIClient
from utils.helpers import INVESTMENT_TYPES, TXN_TYPES


# ─── Transaction type mapping ─────────────────────────────────────────────────
# Maps description keywords from CAMS/KFin statements → our internal txn_type

CAMS_TXN_MAP = {
    # Purchases / SIP
    'purchase':           'BUY',
    'lumpsum':            'BUY',
    'new purchase':       'BUY',
    'additional purchase':'BUY',
    'sip':                'SIP',
    'systematic investment': 'SIP',
    'reinvestment':       'SIP',
    # Redemptions
    'redemption':         'SELL',
    'systematic withdrawal': 'SELL',
    'swp':                'SELL',
    # Switches
    'switch in':          'SWITCH_IN',
    'switch-in':          'SWITCH_IN',
    'switch out':         'SWITCH_OUT',
    'switch-out':         'SWITCH_OUT',
    # Dividends
    'dividend':           'DIVIDEND',
    'idcw':               'DIVIDEND',
}

def map_txn_type(description: str) -> str:
    desc_lower = str(description).lower()
    for keyword, txn_type in CAMS_TXN_MAP.items():
        if keyword in desc_lower:
            return txn_type
    return 'BUY'  # safe default


def parse_date_flexible(val) -> str | None:
    """Try multiple date formats, return YYYY-MM-DD or None."""
    if pd.isna(val) or str(val).strip() == '':
        return None
    s = str(val).strip()
    for fmt in ['%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y',
                '%b %d, %Y', '%d %b %Y', '%Y/%m/%d']:
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


def safe_float(val, default=0.0) -> float:
    try:
        if pd.isna(val):
            return default
        return float(str(val).replace(',', '').strip())
    except Exception:
        return default


# ─── Template DataFrames ──────────────────────────────────────────────────────

INVESTMENT_TEMPLATE = pd.DataFrame([
    {'scheme_name': 'HDFC Mid-Cap Opportunities Fund - Direct - Growth',
     'investment_type': 'MF', 'category': 'Equity - Mid Cap',
     'amc': 'HDFC AMC', 'scheme_code': '118560', 'notes': ''},
    {'scheme_name': 'SBI Small Cap Fund - Direct - Growth',
     'investment_type': 'MF', 'category': 'Equity - Small Cap',
     'amc': 'SBI Funds Management', 'scheme_code': '125494', 'notes': ''},
    {'scheme_name': 'ABC Category II AIF',
     'investment_type': 'AIF', 'category': 'Category II - Private Equity',
     'amc': 'ABC Asset Managers', 'scheme_code': '', 'notes': 'Lock-in 3 years'},
])

TRANSACTION_TEMPLATE = pd.DataFrame([
    {'scheme_name': 'HDFC Mid-Cap Opportunities Fund - Direct - Growth',
     'txn_date': '2024-01-15', 'txn_type': 'BUY',
     'amount': 50000.00, 'units': 312.500, 'nav_at_txn': 160.00, 'notes': 'Lumpsum'},
    {'scheme_name': 'HDFC Mid-Cap Opportunities Fund - Direct - Growth',
     'txn_date': '2024-02-01', 'txn_type': 'SIP',
     'amount': 5000.00, 'units': 29.762, 'nav_at_txn': 168.00, 'notes': 'Monthly SIP'},
    {'scheme_name': 'HDFC Mid-Cap Opportunities Fund - Direct - Growth',
     'txn_date': '2024-06-15', 'txn_type': 'SELL',
     'amount': 10000.00, 'units': 52.083, 'nav_at_txn': 192.00, 'notes': 'Partial redemption'},
])

# CAMS CAS CSV — from casparser tool (casparser /path/to/cas.pdf -p pwd -o out.csv)
# Columns: date, scheme, amc, folio, description, amount, units, nav, balance_units
CAMS_TEMPLATE = pd.DataFrame([
    {'date': '15-Jan-2024', 'scheme': 'HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth Option',
     'amc': 'HDFC Mutual Fund', 'folio': '1234567890',
     'description': 'Purchase', 'amount': 50000.00,
     'units': 312.500, 'nav': 160.00, 'balance_units': 312.500},
    {'date': '01-Feb-2024', 'scheme': 'HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth Option',
     'amc': 'HDFC Mutual Fund', 'folio': '1234567890',
     'description': 'SIP', 'amount': 5000.00,
     'units': 29.762, 'nav': 168.00, 'balance_units': 342.262},
    {'date': '15-Jun-2024', 'scheme': 'HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth Option',
     'amc': 'HDFC Mutual Fund', 'folio': '1234567890',
     'description': 'Redemption', 'amount': 10000.00,
     'units': 52.083, 'nav': 192.00, 'balance_units': 290.179},
    {'date': '01-Mar-2024', 'scheme': 'SBI Small Cap Fund - Direct Plan - Growth',
     'amc': 'SBI Funds Management Pvt. Ltd.', 'folio': '9876543210',
     'description': 'SIP', 'amount': 5000.00,
     'units': 60.241, 'nav': 83.00, 'balance_units': 60.241},
])

# KFintech CAS CSV — same casparser tool handles KFin/Karvy statements
# Columns: date, scheme, amc, folio, description, amount, units, nav, balance_units
KFIN_TEMPLATE = pd.DataFrame([
    {'date': '10-Jan-2024', 'scheme': 'Nippon India Small Cap Fund - Direct Growth Plan',
     'amc': 'Nippon Life India Asset Management Limited', 'folio': '5556667778',
     'description': 'Purchase', 'amount': 25000.00,
     'units': 256.410, 'nav': 97.50, 'balance_units': 256.410},
    {'date': '10-Feb-2024', 'scheme': 'Nippon India Small Cap Fund - Direct Growth Plan',
     'amc': 'Nippon Life India Asset Management Limited', 'folio': '5556667778',
     'description': 'SIP - New Registration', 'amount': 5000.00,
     'units': 48.780, 'nav': 102.50, 'balance_units': 305.190},
    {'date': '01-Mar-2024', 'scheme': 'UTI Nifty 50 Index Fund - Direct Growth Plan',
     'amc': 'UTI Asset Management Company Limited', 'folio': '1112223334',
     'description': 'New Purchase', 'amount': 10000.00,
     'units': 108.342, 'nav': 92.30, 'balance_units': 108.342},
])


# ─── Main render ──────────────────────────────────────────────────────────────

def render():
    st.markdown("## 📤 Import / Export")

    tab_export, tab_own, tab_cams, tab_kfin = st.tabs([
        "⬇️ Export",
        "📥 Our Template",
        "📥 CAMS Statement",
        "📥 KFintech Statement",
    ])

    # ── Export ────────────────────────────────────────────────────────────
    with tab_export:
        _render_export()

    # ── Our own CSV template ──────────────────────────────────────────────
    with tab_own:
        _render_own_template()

    # ── CAMS import ───────────────────────────────────────────────────────
    with tab_cams:
        _render_cams_import()

    # ── KFintech import ───────────────────────────────────────────────────
    with tab_kfin:
        _render_kfin_import()


# ─── Export ───────────────────────────────────────────────────────────────────

def _render_export():
    st.markdown("#### Export Your Portfolio Data")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Investments CSV**")
        if st.button("📊 Generate Investments CSV", key="exp_inv"):
            resp = APIClient.get_investments()
            investments = resp.get('investments', []) if resp else []
            if investments:
                df = pd.DataFrame([{
                    'investment_id': i['investment_id'],
                    'scheme_name': i.get('scheme_name', ''),
                    'investment_type': i.get('investment_type', ''),
                    'category': i.get('category', ''),
                    'amc': i.get('amc', ''),
                    'scheme_code': i.get('scheme_code', ''),
                    'latest_nav': i.get('latest_nav', ''),
                    'latest_nav_date': i.get('latest_nav_date', ''),
                    'manual_current_value': i.get('manual_current_value', ''),
                    'is_active': i.get('is_active', True),
                    'notes': i.get('notes', ''),
                } for i in investments])
                st.download_button("⬇️ Download",
                    data=df.to_csv(index=False),
                    file_name=f"investments_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="dl_inv")
            else:
                st.info("No investments to export.")

    with col2:
        st.markdown("**All Transactions CSV**")
        if st.button("📊 Generate Transactions CSV", key="exp_txn"):
            resp_inv = APIClient.get_investments()
            investments_all = resp_inv.get('investments', []) if resp_inv else []
            all_txns = []
            for inv in investments_all:
                txn_resp = APIClient.get_transactions(inv['investment_id'])
                for t in (txn_resp.get('transactions', []) if txn_resp else []):
                    all_txns.append({
                        'scheme_name': inv['scheme_name'],
                        'investment_type': inv.get('investment_type', ''),
                        'txn_date': t['txn_date'],
                        'txn_type': t['txn_type'],
                        'amount': float(t['amount']),
                        'units': float(t.get('units', 0)),
                        'nav_at_txn': float(t.get('nav_at_txn', 0)),
                        'notes': t.get('notes', ''),
                    })
            if all_txns:
                df = pd.DataFrame(all_txns)
                st.download_button("⬇️ Download",
                    data=df.to_csv(index=False),
                    file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="dl_txn")
            else:
                st.info("No transactions to export.")

    st.divider()
    st.markdown("#### Download Blank Templates")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.download_button("📄 Investments", INVESTMENT_TEMPLATE.to_csv(index=False),
            "investments_template.csv", "text/csv", key="tmpl_inv")
    with c2:
        st.download_button("📄 Transactions", TRANSACTION_TEMPLATE.to_csv(index=False),
            "transactions_template.csv", "text/csv", key="tmpl_txn")
    with c3:
        st.download_button("📄 CAMS Template", CAMS_TEMPLATE.to_csv(index=False),
            "cams_template.csv", "text/csv", key="tmpl_cams")
    with c4:
        st.download_button("📄 KFintech Template", KFIN_TEMPLATE.to_csv(index=False),
            "kfin_template.csv", "text/csv", key="tmpl_kfin")


# ─── Our own template ─────────────────────────────────────────────────────────

def _render_own_template():
    st.markdown("#### Import Using Our CSV Template")

    tab_i, tab_t = st.tabs(["Investments CSV", "Transactions CSV"])

    with tab_i:
        st.caption("Columns: `scheme_name`, `investment_type` (MF/AIF/PMS), `category`, `amc`, `scheme_code`, `notes`")
        uploaded = st.file_uploader("Upload Investments CSV", type="csv", key="own_inv_upload")
        if uploaded:
            _import_investments_csv(pd.read_csv(uploaded))

    with tab_t:
        st.caption("Columns: `scheme_name`, `txn_date` (YYYY-MM-DD), `txn_type` (BUY/SIP/SELL/DIVIDEND), `amount`, `units`, `nav_at_txn`, `notes`")
        uploaded = st.file_uploader("Upload Transactions CSV", type="csv", key="own_txn_upload")
        if uploaded:
            inv_map = _load_investment_map()
            _import_transactions_csv(pd.read_csv(uploaded), inv_map)


# ─── CAMS import ──────────────────────────────────────────────────────────────

def _render_cams_import():
    st.markdown("#### Import from CAMS CAS Statement")

    with st.expander("📋 How to get your CAMS CSV", expanded=True):
        st.markdown("""
**Step 1** — Get your CAS PDF from CAMS:
- Visit [camsonline.com → Statements → CAS](https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement)
- Select **Detailed** statement type, choose your date range
- You'll receive a password-protected PDF by email

**Step 2** — Convert the PDF to CSV using **casparser** (free, open source):
```
pip install casparser
casparser your_cas.pdf -p your_pdf_password -o cas_transactions.csv
```
Or use the free online tool at [casparser.in](https://app.casparser.in)

**Step 3** — Upload the resulting `cas_transactions.csv` below

> **Note:** MFCentral was shut down by SEBI/AMFI in September 2025. CAMS is now the primary source for consolidated MF statements.

**Expected columns:** `date`, `scheme`, `amc`, `folio`, `description`, `amount`, `units`, `nav`, `balance_units`
        """)

    uploaded = st.file_uploader("Upload CAMS CSV (from casparser)", type="csv", key="cams_upload")
    if uploaded:
        df = pd.read_csv(uploaded)
        _import_cas_csv(df, source="CAMS")


# ─── KFintech import ──────────────────────────────────────────────────────────

def _render_kfin_import():
    st.markdown("#### Import from KFintech CAS Statement")

    with st.expander("📋 How to get your KFintech CSV", expanded=True):
        st.markdown("""
**Step 1** — Get your CAS PDF from KFintech:
- Visit [kfintech.com → MF Investors → Statement](https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement)
- Select **Detailed** statement, set your date range
- You'll receive a password-protected PDF by email

**Step 2** — Convert to CSV using **casparser** (same tool as CAMS — it auto-detects KFin format):
```
pip install casparser
casparser your_kfin_cas.pdf -p your_pdf_password -o kfin_transactions.csv
```

**Step 3** — Upload the resulting CSV below

> KFintech covers fund houses like Nippon India, UTI, PGIM, Mirae Asset, Kotak, Franklin, Axis, and DSP.
> CAMS covers HDFC, ICICI Prudential, SBI, Aditya Birla, Tata, PPFAS, Edelweiss, and Invesco.

**Expected columns:** `date`, `scheme`, `amc`, `folio`, `description`, `amount`, `units`, `nav`, `balance_units`
        """)

    uploaded = st.file_uploader("Upload KFintech CSV (from casparser)", type="csv", key="kfin_upload")
    if uploaded:
        df = pd.read_csv(uploaded)
        _import_cas_csv(df, source="KFintech")


# ─── Shared CAS import logic (CAMS and KFin have identical CSV structure) ─────

def _import_cas_csv(df: pd.DataFrame, source: str):
    """
    Parse a casparser-generated CSV and import investments + transactions.
    casparser CSV columns:
      date, scheme, amc, folio, description, amount, units, nav, balance_units
    """
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    # Normalise column name variants
    col_map = {
        'fund': 'scheme', 'fund_name': 'scheme', 'scheme_name': 'scheme',
        'transaction_description': 'description', 'transaction_type': 'description',
        'purchased_units': 'units', 'redeemed_units': 'units',
        'purchase_amount': 'amount', 'net_amount': 'amount',
        'net_asset_value': 'nav', 'nav_per_unit': 'nav',
        'cumulative_units': 'balance_units',
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = {'date', 'scheme', 'amount'}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}. "
                 f"Found columns: {', '.join(df.columns)}")
        st.info("Make sure you exported using `casparser ... -o file.csv`")
        return

    st.success(f"✅ Loaded {len(df)} rows from {source} CSV")
    st.dataframe(df.head(8), use_container_width=True)

    # Build unique scheme list
    schemes = df['scheme'].dropna().unique()
    st.markdown(f"**Found {len(schemes)} unique schemes:**")
    for s in schemes:
        st.caption(f"  • {s}")

    st.divider()

    # Load existing investments so we can match or create
    inv_map = _load_investment_map()

    # Show mapping UI
    st.markdown("#### Match Schemes to Investments")
    st.caption("Schemes already in your portfolio are matched automatically. New ones will be created.")

    scheme_to_inv_id = {}
    new_schemes = []

    for scheme in schemes:
        amc_val = ''
        rows = df[df['scheme'] == scheme]
        if 'amc' in df.columns and not rows['amc'].isna().all():
            amc_val = str(rows['amc'].iloc[0])

        # Fuzzy match — look for scheme name substring in existing investments
        matched_id = None
        for existing_name, inv_id in inv_map.items():
            # Match if 40+ chars of scheme name overlap
            scheme_words = set(scheme.lower().split())
            existing_words = set(existing_name.lower().split())
            if len(scheme_words & existing_words) >= 3:
                matched_id = inv_id
                break

        col_a, col_b = st.columns([3, 2])
        with col_a:
            st.markdown(f"**{scheme[:60]}{'...' if len(scheme) > 60 else ''}**")
            st.caption(f"AMC: {amc_val}")
        with col_b:
            options = ['[Create New]'] + list(inv_map.keys())
            default_idx = 0
            if matched_id:
                matched_name = next(n for n, i in inv_map.items() if i == matched_id)
                if matched_name in options:
                    default_idx = options.index(matched_name)

            sel = st.selectbox("Map to", options, index=default_idx,
                               key=f"map_{hash(scheme)}")
            if sel == '[Create New]':
                new_schemes.append((scheme, amc_val))
                scheme_to_inv_id[scheme] = None
            else:
                scheme_to_inv_id[scheme] = inv_map[sel]

    st.divider()

    if st.button(f"✅ Import from {source}", type="primary", key=f"do_import_{source}"):
        total_created_inv = 0
        total_txns = 0
        errors = 0

        with st.spinner("Importing..."):
            # 1. Create new investments
            for scheme_name, amc_val in new_schemes:
                result = APIClient.create_investment({
                    'scheme_name': scheme_name,
                    'investment_type': 'MF',
                    'category': '',
                    'amc': amc_val,
                    'scheme_code': '',
                    'notes': f'Imported from {source}'
                })
                if result:
                    scheme_to_inv_id[scheme_name] = result['investment_id']
                    total_created_inv += 1

            # 2. Import transactions
            progress = st.progress(0)
            for idx, row in df.iterrows():
                scheme = row.get('scheme', '')
                inv_id = scheme_to_inv_id.get(scheme)
                if not inv_id:
                    errors += 1
                    continue

                txn_date = parse_date_flexible(row.get('date', ''))
                if not txn_date:
                    errors += 1
                    continue

                description = str(row.get('description', ''))
                txn_type = map_txn_type(description)
                amount = safe_float(row.get('amount', 0))
                units = safe_float(row.get('units', 0))
                nav = safe_float(row.get('nav', 0))

                if amount == 0:
                    continue  # Skip zero-amount rows (e.g. balance lines)

                result = APIClient.add_transaction({
                    'investment_id': inv_id,
                    'txn_date': txn_date,
                    'txn_type': txn_type,
                    'amount': abs(amount),
                    'units': abs(units),
                    'nav_at_txn': nav,
                    'notes': description,
                })
                if result:
                    total_txns += 1
                else:
                    errors += 1

                progress.progress((idx + 1) / len(df))

        st.success(f"✅ Created {total_created_inv} new investments, "
                   f"imported {total_txns} transactions. {errors} skipped.")

        if total_txns > 0:
            with st.spinner("Recalculating XIRR for all investments..."):
                APIClient.calculate_xirr()
            st.info("XIRR recalculation triggered. Check Dashboard in a few seconds.")


# ─── Own template import helpers ──────────────────────────────────────────────

def _import_investments_csv(df: pd.DataFrame):
    df.columns = [c.strip().lower() for c in df.columns]
    required = ['scheme_name', 'investment_type']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        return

    st.markdown(f"**Preview** — {len(df)} rows")
    st.dataframe(df.head(10), use_container_width=True)

    if st.button("✅ Import Investments", type="primary", key="do_own_inv"):
        success, errors = 0, 0
        progress = st.progress(0)
        for idx, row in df.iterrows():
            try:
                result = APIClient.create_investment({
                    'scheme_name': str(row.get('scheme_name', '')).strip(),
                    'investment_type': str(row.get('investment_type', 'MF')).strip(),
                    'category': str(row.get('category', '')).strip(),
                    'amc': str(row.get('amc', '')).strip(),
                    'scheme_code': str(row.get('scheme_code', '')).strip(),
                    'notes': str(row.get('notes', '')).strip(),
                })
                if result:
                    success += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            progress.progress((idx + 1) / len(df))
        st.success(f"Imported {success} investments. {errors} errors.")


def _import_transactions_csv(df: pd.DataFrame, inv_map: dict):
    df.columns = [c.strip().lower() for c in df.columns]
    required = ['scheme_name', 'txn_date', 'txn_type', 'amount']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        return

    st.markdown(f"**Preview** — {len(df)} rows")
    st.dataframe(df.head(10), use_container_width=True)

    unmatched = [s for s in df['scheme_name'].unique() if s not in inv_map]
    if unmatched:
        st.warning(f"⚠️ These schemes not found — add them to Investments first: "
                   f"{', '.join(str(u) for u in unmatched[:5])}")

    if st.button("✅ Import Transactions", type="primary", key="do_own_txn"):
        success, errors = 0, 0
        progress = st.progress(0)
        for idx, row in df.iterrows():
            inv_id = inv_map.get(str(row.get('scheme_name', '')).strip())
            if not inv_id:
                errors += 1
                continue
            txn_date = parse_date_flexible(row.get('txn_date', ''))
            if not txn_date:
                errors += 1
                continue
            try:
                result = APIClient.add_transaction({
                    'investment_id': inv_id,
                    'txn_date': txn_date,
                    'txn_type': str(row.get('txn_type', 'BUY')).strip().upper(),
                    'amount': safe_float(row.get('amount', 0)),
                    'units': safe_float(row.get('units', 0)),
                    'nav_at_txn': safe_float(row.get('nav_at_txn', 0)),
                    'notes': str(row.get('notes', '')).strip(),
                })
                if result:
                    success += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            progress.progress((idx + 1) / len(df))

        st.success(f"Imported {success} transactions. {errors} errors.")
        if success > 0:
            APIClient.calculate_xirr()


def _load_investment_map() -> dict:
    """Return {scheme_name: investment_id} for all existing investments."""
    resp = APIClient.get_investments()
    return {
        i['scheme_name']: i['investment_id']
        for i in (resp.get('investments', []) if resp else [])
    }
