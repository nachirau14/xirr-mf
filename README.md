# 📊 MF / AIF / PMS XIRR Tracker

A full-stack portfolio tracker for Mutual Funds, Alternative Investment Funds (AIF), and Portfolio Management Services (PMS) — with automatic NAV fetching, XIRR calculation, weekly email digests, and a Streamlit frontend.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Streamlit Community Cloud               │
│  app.py  →  pages/  →  utils/api.py → API Gateway  │
└────────────────────────┬────────────────────────────┘
                         │ HTTPS REST
┌────────────────────────▼────────────────────────────┐
│                    AWS Backend                       │
│                                                      │
│  API Gateway → Lambda (api_handler)                  │
│                    ├── DynamoDB (investments)         │
│                    ├── DynamoDB (transactions)        │
│                    ├── DynamoDB (nav_history)         │
│                    └── DynamoDB (xirr_cache)         │
│                                                      │
│  EventBridge (daily 10PM IST)                        │
│    └── Lambda (nav_fetcher) → AMFI India API         │
│                                                      │
│  EventBridge (Monday 9AM IST)                        │
│    └── Lambda (weekly_digest) → AWS SES              │
│                                                      │
│  Lambda (xirr_calculator) — invoked on demand        │
└─────────────────────────────────────────────────────┘
```

---

## DynamoDB Table Schema

### `mf-investments-prod`
| Field | Type | Notes |
|---|---|---|
| `user_id` | PK (String) | e.g. `"user_admin_001"` |
| `investment_id` | SK (String) | UUID |
| `scheme_name` | String | Fund name |
| `investment_type` | String | `MF`, `AIF`, `PMS` |
| `category` | String | e.g. `Equity - Mid Cap` |
| `scheme_code` | String | AMFI code (MF only) |
| `amc` | String | Fund house name |
| `latest_nav` | Decimal | Updated daily by NAV fetcher |
| `latest_nav_date` | String | YYYY-MM-DD |
| `manual_current_value` | Decimal | For AIF/PMS |
| `is_active` | Boolean | Soft delete flag |
| `notes` | String | Free text |

### `mf-transactions-prod`
| Field | Type | Notes |
|---|---|---|
| `investment_id` | PK (String) | Links to investments table |
| `txn_id` | SK (String) | UUID |
| `txn_date` | String | YYYY-MM-DD |
| `txn_type` | String | `BUY`, `SELL`, `SIP`, `DIVIDEND` |
| `amount` | Decimal | In INR |
| `units` | Decimal | Units bought/sold |
| `nav_at_txn` | Decimal | NAV on transaction date |
| `notes` | String | |

### `mf-nav-history-prod`
| Field | Type | Notes |
|---|---|---|
| `scheme_code` | PK (String) | AMFI code or `MANUAL#<inv_id>` |
| `nav_date` | SK (String) | YYYY-MM-DD |
| `nav` | Decimal | NAV value |
| `is_manual` | Boolean | True for AIF/PMS entries |
| `ttl` | Number | Auto-expire after 5 years |

---

## Deployment Guide

### Prerequisites
- AWS CLI configured (`aws configure`)
- Python 3.11+
- Verified SES email address (for digest emails)
- A GitHub account for Streamlit Community Cloud

---

### Step 1 — Verify SES Email

```bash
aws ses verify-email-identity \
  --email-address noreply@yourdomain.com \
  --region ap-south-1
```

Also verify all **recipient** emails while you're in SES sandbox.

> To send to unverified emails, request SES production access in the AWS console.

---

### Step 2 — Deploy Backend

```bash
cd backend
chmod +x deploy.sh
./deploy.sh prod ap-south-1 noreply@yourdomain.com "you@gmail.com,spouse@gmail.com"
```

The script will:
1. Create an S3 bucket for Lambda artifacts
2. Package all 4 Lambda functions
3. Deploy CloudFormation stack (DynamoDB, Lambda, API Gateway, EventBridge)
4. Output the API endpoint URL

**Save the API endpoint URL** — you'll need it in Step 4.

---

### Step 3 — Generate a Password Hash

Run this locally to hash your password:

```python
import hashlib
password = "changeme"
print(hashlib.sha256(password.encode()).hexdigest())
```

057ba03d6c44104863dc7361fe4578965d1887360f90a0895882e58a6248fc86

Or use the Settings page after first login (using the default `admin`/`admin` credentials).

---

### Step 4 — Configure Streamlit Secrets

In Streamlit Community Cloud → your app → **Settings → Secrets**, paste:

```toml
API_BASE_URL = "https://YOUR_API.ap-south-1.amazonaws.com/prod"

[users]
admin = "057ba03d6c44104863dc7361fe4578965d1887360f90a0895882e58a6248fc86"
admin_id = "admin"

nachi = "057ba03d6c44104863dc7361fe4578965d1887360f90a0895882e58a6248fc86"
nachi_id = "nachi"
```

---

### Step 5 — Deploy Frontend to Streamlit Community Cloud

1. Push the `frontend/` folder to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path:** `app.py`
5. Add secrets from Step 4
6. Click **Deploy**

---

## Adding Investments

### Mutual Funds
1. Go to **Scheme Search** and find the AMFI scheme code
2. Go to **Investments → Add Investment**, enter the scheme code
3. NAVs will be fetched automatically every evening

### AIF / PMS
1. Go to **Investments → Add Investment**, select type `AIF` or `PMS`
2. Leave `scheme_code` blank
3. Use **Investments → Manual NAV Entry** to update values periodically

### Bulk Upload
1. Download the CSV template from **Import/Export**
2. Fill it in with your data
3. Upload via **Import/Export → Import Investments** then **Import Transactions**

---

## XIRR Calculation

XIRR is computed using the Newton-Raphson method (same as Excel's `XIRR` function):

- **Outflows** (BUY/SIP): negative cash flows
- **Inflows** (SELL + current portfolio value): positive cash flows
- **Current value date**: today
- **Result**: annualized rate of return

For MF: Current value = `units_held × latest_AMFI_NAV`  
For AIF/PMS: Current value = last manually entered value

---

## Weekly Digest Email

Sent every **Monday at ~9 AM IST** containing:
- Total invested vs current value
- Week-over-week change
- Per-investment XIRR comparison
- Table of all holdings with NAVs

---

## Local Development

```bash
# Backend: test individual Lambdas
cd backend
python -c "
import json
from lambdas.nav_fetcher.handler import lambda_handler
result = lambda_handler({}, None)
print(json.dumps(result, indent=2))
"

# Frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

For local frontend, create `.streamlit/secrets.toml` from the template.

---

## File Structure

```
mf-tracker/
├── backend/
│   ├── cloudformation/
│   │   └── template.yaml           # Full AWS stack definition
│   ├── lambdas/
│   │   ├── nav_fetcher/
│   │   │   └── handler.py          # Daily AMFI NAV fetch
│   │   ├── xirr_calculator/
│   │   │   └── handler.py          # XIRR computation engine
│   │   ├── api_handler/
│   │   │   └── handler.py          # REST API (investments, transactions, NAV)
│   │   └── weekly_digest/
│   │       └── handler.py          # HTML email digest via SES
│   └── deploy.sh                   # One-command deployment script
│
└── frontend/
    ├── app.py                       # Entry point + auth
    ├── requirements.txt
    ├── .streamlit/
    │   ├── config.toml             # Theme + server config
    │   └── secrets.toml.template  # Copy & fill for deployment
    ├── pages/
    │   ├── dashboard.py            # Portfolio overview + charts
    │   ├── investments.py          # CRUD + manual NAV entry
    │   ├── transactions.py         # Transaction history + XIRR detail
    │   ├── analytics.py            # Comparison charts + aggregated XIRR
    │   ├── scheme_search.py        # AMFI scheme lookup
    │   ├── import_export.py        # CSV bulk upload + export
    │   └── settings.py            # Password hash gen + info
    └── utils/
        ├── api.py                  # API client (all backend calls)
        └── helpers.py             # Constants, XIRR, formatters
```
