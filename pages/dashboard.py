"""
Dashboard Page — Portfolio overview with XIRR metrics.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api import APIClient
from utils.helpers import format_inr, format_xirr, color_return, compute_xirr_local
from datetime import datetime


def render():
    st.markdown("## 🏠 Portfolio Dashboard")
    
    col_refresh, col_calc = st.columns([6, 1])
    with col_calc:
        if st.button("🔄 Recalculate", type="secondary", use_container_width=True):
            with st.spinner("Recalculating XIRR..."):
                APIClient.calculate_xirr()
            st.success("XIRR recalculated!")
    
    # ─── Fetch data ───────────────────────────────────────────────────────
    with st.spinner("Loading portfolio..."):
        analytics_resp = APIClient.get_analytics()
    
    if not analytics_resp or not analytics_resp.get('analytics'):
        st.info("No investments found. Add your first investment from the **Investments** page.")
        return
    
    investments = analytics_resp['analytics']
    
    # ─── Summary metrics ──────────────────────────────────────────────────
    total_invested = sum(i.get('total_invested', 0) for i in investments)
    total_current = sum(i.get('current_value', 0) for i in investments)
    total_gain = total_current - total_invested
    total_gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0
    
    # Aggregate XIRR across all (fetch cached)
    all_ids = [i['investment_id'] for i in investments]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Invested", format_inr(total_invested))
    with col2:
        st.metric("Current Value", format_inr(total_current),
                  delta=format_inr(total_gain))
    with col3:
        gain_color = "normal" if total_gain >= 0 else "inverse"
        st.metric("Absolute Return", f"{total_gain_pct:+.2f}%")
    with col4:
        st.metric("Holdings", f"{len(investments)} funds")
    
    st.divider()
    
    # ─── Allocation donut charts ──────────────────────────────────────────
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("#### Allocation by Type")
        by_type = {}
        for inv in investments:
            t = inv.get('investment_type', 'MF')
            by_type[t] = by_type.get(t, 0) + inv.get('current_value', 0)
        
        if by_type:
            fig = px.pie(
                names=list(by_type.keys()),
                values=list(by_type.values()),
                hole=0.55,
                color_discrete_sequence=['#0f3460', '#16213e', '#533483']
            )
            fig.update_traces(textposition='outside', textinfo='percent+label')
            fig.update_layout(
                showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        st.markdown("#### Allocation by Category")
        by_cat = {}
        for inv in investments:
            c = inv.get('category', 'Other') or 'Other'
            by_cat[c] = by_cat.get(c, 0) + inv.get('current_value', 0)
        
        top_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:8]
        if top_cats:
            fig = px.bar(
                x=[v for _, v in top_cats],
                y=[k for k, _ in top_cats],
                orientation='h',
                color_discrete_sequence=['#0f3460'],
                labels={'x': 'Value (₹)', 'y': ''}
            )
            fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=50),
                              showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ─── Investment table ─────────────────────────────────────────────────
    st.markdown("#### Holdings")
    
    rows = []
    for inv in investments:
        xirr_cached = None
        try:
            cached = APIClient.get_cached_xirr(inv['investment_id'])
            if cached and cached.get('xirr') is not None:
                xirr_cached = cached['xirr']
        except Exception:
            pass
        
        gain = inv.get('current_value', 0) - inv.get('total_invested', 0)
        rows.append({
            'Scheme': inv['scheme_name'],
            'Type': inv.get('investment_type', 'MF'),
            'Category': inv.get('category', ''),
            'Invested': inv.get('total_invested', 0),
            'Current Value': inv.get('current_value', 0),
            'Gain/Loss': gain,
            'Return %': inv.get('absolute_return_pct', 0),
            'XIRR %': xirr_cached,
            'Latest NAV': inv.get('latest_nav', 0),
            'NAV Date': inv.get('latest_nav_date', '')
        })
    
    if rows:
        df = pd.DataFrame(rows)
        
        def color_val(val):
            if pd.isna(val) or val == 0:
                return 'color: gray'
            return f'color: {"#2ecc71" if val > 0 else "#e74c3c"}'
        
        styled = df.style.format({
            'Invested': lambda x: format_inr(x),
            'Current Value': lambda x: format_inr(x),
            'Gain/Loss': lambda x: format_inr(x),
            'Return %': lambda x: f'{x:+.2f}%' if x else '—',
            'XIRR %': lambda x: f'{x:+.2f}%' if x else '—',
            'Latest NAV': lambda x: f'₹{x:,.4f}' if x else '—',
        }).applymap(color_val, subset=['Gain/Loss', 'Return %', 'XIRR %'])
        
        st.dataframe(styled, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ─── Type-wise summary ────────────────────────────────────────────────
    st.markdown("#### Summary by Investment Type")
    type_summary = {}
    for inv in investments:
        t = inv.get('investment_type', 'MF')
        if t not in type_summary:
            type_summary[t] = {'invested': 0, 'current': 0, 'count': 0}
        type_summary[t]['invested'] += inv.get('total_invested', 0)
        type_summary[t]['current'] += inv.get('current_value', 0)
        type_summary[t]['count'] += 1
    
    cols = st.columns(len(type_summary) or 1)
    for i, (inv_type, data) in enumerate(type_summary.items()):
        gain = data['current'] - data['invested']
        gain_pct = (gain / data['invested'] * 100) if data['invested'] > 0 else 0
        with cols[i]:
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:16px;
                        box-shadow:0 2px 8px rgba(0,0,0,0.08);
                        border-top:4px solid {'#0f3460' if inv_type=='MF' else '#533483' if inv_type=='AIF' else '#e94560'}">
                <div style="font-size:12px;color:#888;text-transform:uppercase">{inv_type} · {data['count']} funds</div>
                <div style="font-size:20px;font-weight:700;margin:6px 0">{format_inr(data['current'])}</div>
                <div style="font-size:13px;color:{'#2ecc71' if gain >= 0 else '#e74c3c'}">
                    {'+' if gain >= 0 else ''}{format_inr(gain)} ({gain_pct:+.2f}%)
                </div>
            </div>
            """, unsafe_allow_html=True)
