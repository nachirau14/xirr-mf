"""
Analytics Page — Comparison charts, aggregated XIRR calculator, performance ranking.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api import APIClient
from utils.helpers import format_inr, compute_xirr_local, INVESTMENT_TYPES
from datetime import datetime


def render():
    st.markdown("## 📈 Analytics & Comparison")
    
    with st.spinner("Loading analytics..."):
        resp = APIClient.get_analytics()
    
    if not resp or not resp.get('analytics'):
        st.info("No investment data available.")
        return
    
    investments = resp['analytics']
    
    tab_compare, tab_agg_xirr, tab_trends = st.tabs([
        "📊 Compare Returns", "🧮 Aggregated XIRR Calculator", "📉 Performance Ranking"
    ])
    
    # ─── Tab 1: Compare Returns ───────────────────────────────────────────
    with tab_compare:
        st.markdown("#### Relative Return Comparison")
        
        # Filter controls
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_type = st.multiselect("Investment Type", INVESTMENT_TYPES,
                                         default=INVESTMENT_TYPES, key="analytics_type_filter")
        with col_f2:
            sort_by = st.selectbox("Sort by", ["Return %", "XIRR %", "Current Value", "Invested"], key="analytics_sort")
        
        filtered = [i for i in investments if i.get('investment_type') in filter_type]
        
        if not filtered:
            st.info("No investments match filters.")
        else:
            # Waterfall / bar chart of returns
            df = pd.DataFrame([{
                'Scheme': i['scheme_name'][:35] + ('...' if len(i['scheme_name']) > 35 else ''),
                'Type': i.get('investment_type', 'MF'),
                'Category': i.get('category', ''),
                'Invested': i.get('total_invested', 0),
                'Current Value': i.get('current_value', 0),
                'Return %': i.get('absolute_return_pct', 0),
                'Absolute Gain': i.get('absolute_gain', 0),
            } for i in filtered])
            
            # Sort
            sort_col = {'Return %': 'Return %', 'XIRR %': 'Return %', 'Current Value': 'Current Value', 'Invested': 'Invested'}[sort_by]
            df = df.sort_values(sort_col, ascending=True)
            
            # Horizontal bar chart
            colors = df['Return %'].apply(lambda x: '#2ecc71' if x >= 0 else '#e74c3c')
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=df['Scheme'],
                x=df['Return %'],
                orientation='h',
                marker_color=colors,
                text=df['Return %'].apply(lambda x: f'{x:+.2f}%'),
                textposition='outside'
            ))
            fig.update_layout(
                title='Absolute Return % by Investment',
                height=max(300, len(df) * 35),
                xaxis_title='Return %',
                yaxis_title='',
                showlegend=False,
                margin=dict(l=10, r=60)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Invested vs current value grouped bar
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                name='Invested', x=df['Scheme'], y=df['Invested'],
                marker_color='#0f3460'
            ))
            fig2.add_trace(go.Bar(
                name='Current Value', x=df['Scheme'], y=df['Current Value'],
                marker_color='#2ecc71'
            ))
            fig2.update_layout(
                barmode='group',
                title='Invested vs Current Value',
                height=380,
                xaxis_title='',
                yaxis_title='Value (₹)',
                margin=dict(l=10, r=10)
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    # ─── Tab 2: Aggregated XIRR Calculator ───────────────────────────────
    with tab_agg_xirr:
        st.markdown("#### Custom Group XIRR Calculator")
        st.caption("Select any combination of investments to compute aggregate XIRR.")
        
        all_names = {i['scheme_name']: i['investment_id'] for i in investments}
        
        selected_names = st.multiselect(
            "Select investments to aggregate",
            options=list(all_names.keys()),
            default=list(all_names.keys()),
            key="agg_xirr_select"
        )
        
        if st.button("🧮 Calculate Aggregate XIRR", type="primary", key="calc_agg_xirr"):
            if not selected_names:
                st.warning("Select at least one investment.")
            else:
                selected_ids = [all_names[n] for n in selected_names]
                
                with st.spinner("Calculating..."):
                    result = APIClient.calculate_xirr(investment_ids=selected_ids)
                
                if result:
                    xirr_body = result
                    # Parse response
                    import json
                    if isinstance(result.get('body'), str):
                        xirr_body = json.loads(result['body'])
                    
                    group_xirr = xirr_body.get('group_xirr')
                    total_inv = xirr_body.get('total_invested', 0)
                    total_val = xirr_body.get('total_current_value', 0)
                    abs_ret = xirr_body.get('absolute_return_pct', 0)
                    
                    st.divider()
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Group XIRR", f"{group_xirr:+.2f}%" if group_xirr else "—")
                    with col2:
                        st.metric("Total Invested", format_inr(total_inv))
                    with col3:
                        st.metric("Total Current Value", format_inr(total_val))
                    with col4:
                        st.metric("Absolute Return", f"{abs_ret:+.2f}%")
        
        st.divider()
        st.markdown("#### Quick Local XIRR Calculator")
        st.caption("Enter cash flows manually for a one-off calculation. BUY = negative, SELL/current value = positive.")
        
        num_rows = st.number_input("Number of cash flows", min_value=2, max_value=50, value=3, step=1)
        
        cash_flows_input = []
        for i in range(int(num_rows)):
            c1, c2 = st.columns(2)
            with c1:
                d = st.date_input(f"Date {i+1}", key=f"cf_date_{i}")
            with c2:
                amt = st.number_input(f"Amount {i+1} (negative=outflow)", key=f"cf_amt_{i}", format="%.2f")
            cash_flows_input.append((datetime.combine(d, datetime.min.time()), float(amt)))
        
        if st.button("Calculate XIRR", key="quick_xirr"):
            xirr = compute_xirr_local(cash_flows_input)
            if xirr is not None:
                color = "#2ecc71" if xirr >= 0 else "#e74c3c"
                st.markdown(f"### XIRR: <span style='color:{color}'>{xirr:+.2f}%</span>", unsafe_allow_html=True)
            else:
                st.error("Could not compute XIRR. Check that you have both outflows and inflows.")
    
    # ─── Tab 3: Performance Ranking ───────────────────────────────────────
    with tab_trends:
        st.markdown("#### Performance Ranking")
        
        rows = []
        for inv in investments:
            cached = APIClient.get_cached_xirr(inv['investment_id'])
            xirr_val = cached.get('xirr') if cached else None
            rows.append({
                'Rank': 0,
                'Scheme': inv['scheme_name'],
                'Type': inv.get('investment_type', 'MF'),
                'Category': inv.get('category', ''),
                'Invested': inv.get('total_invested', 0),
                'Current Value': inv.get('current_value', 0),
                'Return %': inv.get('absolute_return_pct', 0),
                'XIRR %': xirr_val,
            })
        
        # Sort by XIRR (nulls last), then return %
        rows.sort(key=lambda x: (x['XIRR %'] is None, -(x['XIRR %'] or x['Return %'])))
        for i, r in enumerate(rows):
            r['Rank'] = i + 1
        
        if rows:
            df = pd.DataFrame(rows)
            
            def highlight_rows(row):
                xirr = row.get('XIRR %')
                if xirr is None:
                    return [''] * len(row)
                color = 'rgba(46, 204, 113, 0.1)' if xirr > 0 else 'rgba(231, 76, 60, 0.1)'
                return [f'background-color: {color}'] * len(row)
            
            styled = df.style.format({
                'Invested': lambda x: format_inr(x),
                'Current Value': lambda x: format_inr(x),
                'Return %': lambda x: f'{x:+.2f}%',
                'XIRR %': lambda x: f'{x:+.2f}%' if x is not None else '—',
            }).apply(highlight_rows, axis=1)
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        
        # Category performance comparison
        st.divider()
        st.markdown("#### Returns by Category")
        by_cat = {}
        for inv in investments:
            cat = inv.get('category', 'Other') or 'Other'
            if cat not in by_cat:
                by_cat[cat] = {'invested': 0, 'current': 0}
            by_cat[cat]['invested'] += inv.get('total_invested', 0)
            by_cat[cat]['current'] += inv.get('current_value', 0)
        
        cat_df = pd.DataFrame([{
            'Category': cat,
            'Return %': ((v['current'] - v['invested']) / v['invested'] * 100) if v['invested'] > 0 else 0,
            'Invested': v['invested'],
            'Current': v['current']
        } for cat, v in by_cat.items()]).sort_values('Return %', ascending=True)
        
        if not cat_df.empty:
            fig = px.bar(cat_df, y='Category', x='Return %', orientation='h',
                         color='Return %',
                         color_continuous_scale=['#e74c3c', '#f39c12', '#2ecc71'],
                         text=cat_df['Return %'].apply(lambda x: f'{x:+.2f}%'))
            fig.update_layout(height=max(300, len(cat_df) * 40), showlegend=False,
                              coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
