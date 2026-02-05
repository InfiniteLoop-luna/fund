import streamlit as st
import time
from datetime import datetime
import plotly.graph_objects as go
from data_fetcher import TushareClient, RealtimeQuoteClient, CacheManager
from calculator import NetValueEstimator

# Page config
st.set_page_config(
    page_title="基金实时估值分析工具",
    page_icon="📈",
    layout="wide"
)

# Custom CSS for professional look
st.markdown("""
<style>
    /* Card container styling */
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Deep blue accent color */
    .stButton>button[kind="primary"] {
        background-color: #1e3a8a !important;
        border-color: #1e3a8a !important;
    }

    .stButton>button[kind="primary"]:hover {
        background-color: #1e40af !important;
        border-color: #1e40af !important;
    }

    /* Metric card styling */
    .metric-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 12px rgba(30, 58, 138, 0.2);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 10px 0;
    }

    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Chinese stock market colors: red for gains, green for losses */
    .gain {
        color: #ef4444 !important;
    }

    .loss {
        color: #22c55e !important;
    }

    /* Section headers */
    .section-header {
        color: #1e3a8a;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #e0e0e0;
    }

    /* Streamlit metric override for Chinese colors */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'fund_code' not in st.session_state:
    st.session_state.fund_code = ""

# Load fund list (cached) - defined at module level for proper caching
@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_fund_list():
    try:
        client = TushareClient()
        df, error = client.get_all_funds()
        if error:
            return None, error
        return df, None
    except Exception as e:
        return None, str(e)

# Sidebar with refresh controls
with st.sidebar:
    st.title("⚙️ 设置")

    # Fund list search section
    st.subheader("📋 基金列表")

    fund_list_df, fund_list_error = load_fund_list()

    if fund_list_error:
        st.error(f"加载基金列表失败: {fund_list_error}")
    elif fund_list_df is None:
        st.warning("基金列表数据为空")
    elif fund_list_df.empty:
        st.warning("未找到基金数据")
    else:
        # Search box with key to preserve state
        search_term = st.text_input(
            "搜索基金",
            placeholder="输入基金代码或名称",
            help="支持模糊搜索基金代码或名称",
            key="fund_search"
        )

        # Filter funds based on search term
        if search_term:
            filtered_df = fund_list_df[
                fund_list_df['ts_code'].str.contains(search_term, case=False, na=False) |
                fund_list_df['name'].str.contains(search_term, case=False, na=False)
            ]
        else:
            filtered_df = fund_list_df

        # Display fund count
        st.caption(f"共 {len(filtered_df)} 个基金")

        # Fund selection
        if not filtered_df.empty:
            # Create display options: "代码 - 名称"
            # Strip common suffixes for cleaner display but keep full code in data
            fund_options = []
            fund_code_map = {}  # Map display code to full ts_code
            for _, row in filtered_df.iterrows():
                ts_code = row['ts_code']
                # Strip suffix for display
                display_code = ts_code.replace('.OF', '').replace('.SH', '').replace('.SZ', '')
                display_text = f"{display_code} - {row['name']}"
                fund_options.append(display_text)
                fund_code_map[display_text] = ts_code

            selected_fund = st.selectbox(
                "选择基金",
                options=[""] + fund_options,
                format_func=lambda x: "请选择..." if x == "" else x
            )

            if selected_fund and selected_fund != "":
                # Get the full ts_code from the map
                selected_code = fund_code_map[selected_fund]
                if st.button("📊 查看该基金", use_container_width=True, type="primary"):
                    st.session_state.fund_code = selected_code
                    CacheManager.clear_cache()
                    st.rerun()

    st.markdown("---")
    st.subheader("🔍 基金查询")

    # Fund code input in sidebar
    fund_code_input = st.text_input(
        "基金代码",
        value=st.session_state.fund_code,
        placeholder="请输入6位基金代码，如: 000001",
        help="输入基金代码，支持格式: 000001 或 000001.OF",
        key="fund_code_input_sidebar"
    )

    if st.button("🔍 查询", use_container_width=True, type="primary", key="query_button_sidebar"):
        if fund_code_input:
            st.session_state.fund_code = fund_code_input.strip()
            CacheManager.clear_cache()
            st.rerun()

    st.markdown("---")
    st.subheader("刷新设置")

    refresh_options = {
        "手动刷新": 0,
        "15秒": 15,
        "30秒": 30,
        "60秒": 60
    }
    refresh_choice = st.radio("刷新间隔", options=list(refresh_options.keys()), index=0)
    refresh_interval = refresh_options[refresh_choice]

    if st.button("🔄 立即刷新", use_container_width=True):
        CacheManager.clear_cache()
        st.rerun()

    if st.session_state.last_update:
        st.caption(f"最后更新: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Auto-refresh countdown
    if refresh_interval > 0 and st.session_state.last_update:
        elapsed = (datetime.now() - st.session_state.last_update).total_seconds()
        remaining = max(0, refresh_interval - elapsed)
        if remaining > 0:
            st.caption(f"下次刷新: {int(remaining)}秒")
        else:
            time.sleep(0.1)
            st.rerun()

# Main content
st.title("📈 Spark Fund - 基金实时估值分析")
st.markdown("---")

# Fetch and display data
if st.session_state.fund_code:
    try:
        # Initialize clients
        tushare_client = TushareClient()
        quote_client = RealtimeQuoteClient(tushare_client.pro)

        # Fetch fund basic info (with cache)
        cache_key_info = f"cache_fund_info_{st.session_state.fund_code}"
        cached_info = CacheManager.get_cached(cache_key_info, CacheManager.FUND_INFO_TTL)

        if cached_info and not cached_info.is_stale:
            fund_info = cached_info.data
            info_error = None
        else:
            fund_info, info_error = tushare_client.get_fund_basic(st.session_state.fund_code)
            if fund_info:
                CacheManager.set_cached(cache_key_info, fund_info)

        # Fetch holdings (with cache)
        cache_key_holdings = f"cache_holdings_{st.session_state.fund_code}"
        cached_holdings = CacheManager.get_cached(cache_key_holdings, CacheManager.FUND_INFO_TTL)

        if cached_holdings and not cached_holdings.is_stale:
            holdings = cached_holdings.data
            holdings_error = None
        else:
            holdings, holdings_error = tushare_client.get_fund_portfolio(st.session_state.fund_code)
            if holdings:
                CacheManager.set_cached(cache_key_holdings, holdings)

        # Handle errors
        if info_error:
            st.error(f"❌ {info_error}")
            st.stop()

        if holdings_error:
            st.warning(f"⚠️ {holdings_error}")
            holdings = []

        # Fetch real-time quotes
        if holdings:
            stock_codes = [h.stock_code for h in holdings]
            quotes_dict, quotes_error = quote_client.get_realtime_quotes(stock_codes)

            if quotes_error and not quotes_dict:
                st.warning(f"⚠️ {quotes_error}")

            # Calculate estimation
            estimation = NetValueEstimator.calculate_estimated_value(
                fund_info.net_value,
                holdings,
                quotes_dict
            )
        else:
            estimation = None

        st.session_state.last_update = datetime.now()

    except Exception as e:
        st.error(f"❌ 系统错误: {str(e)}")
        st.stop()

    # Top metrics section with Chinese stock market colors (red for gains, green for losses)
    if estimation:
        metric_col1, metric_col2, metric_col3 = st.columns(3)

        # Calculate values
        current_value = estimation.estimated_value
        change_amount = estimation.estimated_value - fund_info.net_value
        change_pct = estimation.estimated_change_pct

        # Determine color class based on Chinese convention
        color_class = "gain" if change_pct > 0 else "loss" if change_pct < 0 else ""
        color_hex = "#ef4444" if change_pct > 0 else "#22c55e" if change_pct < 0 else "#6b7280"

        with metric_col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">当前估值</div>
                <div class="metric-value">{current_value:.4f}</div>
                <div style="font-size: 0.85rem; opacity: 0.8;">基准净值: {fund_info.net_value:.4f}</div>
            </div>
            """, unsafe_allow_html=True)

        with metric_col2:
            change_sign = "+" if change_amount > 0 else ""
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, {color_hex} 0%, {color_hex}dd 100%);">
                <div class="metric-label">盈亏金额</div>
                <div class="metric-value">{change_sign}{change_amount:.4f}</div>
                <div style="font-size: 0.85rem; opacity: 0.8;">单位净值变化</div>
            </div>
            """, unsafe_allow_html=True)

        with metric_col3:
            change_sign = "+" if change_pct > 0 else ""
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, {color_hex} 0%, {color_hex}dd 100%);">
                <div class="metric-label">盈亏比例</div>
                <div class="metric-value">{change_sign}{change_pct:.2f}%</div>
                <div style="font-size: 0.85rem; opacity: 0.8;">相对净值日涨跌</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # Historical trend chart with Plotly
    st.markdown('<div class="section-header">📊 净值走势图</div>', unsafe_allow_html=True)

    # Fetch historical data (with cache)
    cache_key_history = f"cache_history_{st.session_state.fund_code}"
    cached_history = CacheManager.get_cached(cache_key_history, CacheManager.FUND_INFO_TTL)

    if cached_history and not cached_history.is_stale:
        history_df = cached_history.data
        history_error = None
    else:
        history_df, history_error = tushare_client.get_fund_nav_history(st.session_state.fund_code, days=30)
        if history_df is not None:
            CacheManager.set_cached(cache_key_history, history_df)

    if history_error:
        st.warning(f"⚠️ {history_error}")
    elif history_df is not None and not history_df.empty:
        # Convert date strings to datetime for proper x-axis formatting
        import pandas as pd
        history_df['date'] = pd.to_datetime(history_df['date'], format='%Y%m%d')

        # Create Plotly chart with smooth curves and transparent background
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=history_df['date'],
            y=history_df['nav'],
            mode='lines',
            name='单位净值',
            line=dict(
                color='#1e3a8a',
                width=3,
                shape='spline'  # Smooth curve
            ),
            fill='tozeroy',
            fillcolor='rgba(30, 58, 138, 0.1)',
            hovertemplate='<b>日期</b>: %{x}<br><b>净值</b>: %{y:.4f}<extra></extra>'
        ))

        # Add current estimation point if available
        if estimation:
            fig.add_trace(go.Scatter(
                x=[datetime.now()],
                y=[estimation.estimated_value],
                mode='markers',
                name='实时估值',
                marker=dict(
                    color='#ef4444' if estimation.estimated_change_pct > 0 else '#22c55e',
                    size=12,
                    symbol='diamond'
                ),
                hovertemplate='<b>实时估值</b>: %{y:.4f}<extra></extra>'
            ))

        # Calculate y-axis range with padding to show variations more clearly
        y_min = history_df['nav'].min()
        y_max = history_df['nav'].max()

        # Include estimation point in range calculation if available
        if estimation:
            y_min = min(y_min, estimation.estimated_value)
            y_max = max(y_max, estimation.estimated_value)

        y_range = y_max - y_min
        y_padding = max(y_range * 0.1, 0.01)  # 10% padding or at least 0.01

        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                title='日期',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)',
                showline=True,
                linecolor='rgba(0,0,0,0.1)',
                tickformat='%Y-%m-%d',
                dtick=86400000 * 5  # Show tick every 5 days
            ),
            yaxis=dict(
                title='单位净值',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)',
                showline=True,
                linecolor='rgba(0,0,0,0.1)',
                range=[y_min - y_padding, y_max + y_padding]  # Tight range around data
            ),
            hovermode='x unified',
            margin=dict(l=50, r=50, t=30, b=50),
            height=400,
            font=dict(family='Arial, sans-serif', size=12),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无历史数据")

    st.markdown("---")

    # Display results in three columns
    st.markdown("---")
    col_left, col_center, col_right = st.columns([1, 1, 1])

    # Left column - Fund basic info
    with col_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📋 基金信息</div>', unsafe_allow_html=True)
        st.markdown(f"**{fund_info.fund_name}**")
        st.caption(f"代码: {fund_info.fund_code}")
        st.text(f"管理公司: {fund_info.management}")
        st.text(f"基金经理: {fund_info.manager}")
        st.text(f"成立日期: {fund_info.found_date}")
        st.markdown("---")
        st.metric(
            label="最新单位净值",
            value=f"{fund_info.net_value:.4f}",
            help=f"更新日期: {fund_info.net_value_date}"
        )
        st.caption(f"净值日期: {fund_info.net_value_date}")

        if cached_info and cached_info.is_stale:
            st.warning("⚠️ 显示缓存数据")
        st.markdown('</div>', unsafe_allow_html=True)

    # Center column - Real-time estimation
    with col_center:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">💹 实时估值</div>', unsafe_allow_html=True)

        if estimation:
            # Market status
            if estimation.is_market_open:
                st.success("🟢 交易中")
            else:
                st.info("🔒 休市")

            # Estimated value with Chinese colors
            change_color = "#ef4444" if estimation.estimated_change_pct > 0 else "#22c55e" if estimation.estimated_change_pct < 0 else "#6b7280"

            st.markdown(
                f"<h1 style='text-align: center; color: {change_color};'>{estimation.estimated_value:.4f}</h1>",
                unsafe_allow_html=True
            )

            # Change percentage
            change_sign = "+" if estimation.estimated_change_pct > 0 else ""
            st.markdown(
                f"<h3 style='text-align: center; color: {change_color};'>{change_sign}{estimation.estimated_change_pct:.2f}%</h3>",
                unsafe_allow_html=True
            )

            st.markdown("---")

            # Confidence and coverage
            col_conf, col_cov = st.columns(2)
            with col_conf:
                confidence_emoji = "🟢" if estimation.confidence == "high" else "🟡" if estimation.confidence == "medium" else "🔴"
                st.metric("置信度", f"{confidence_emoji} {estimation.confidence.upper()}")
            with col_cov:
                st.metric("覆盖率", f"{estimation.coverage_pct:.0f}%")

            # Warnings
            if estimation.warnings:
                st.markdown("**⚠️ 提示:**")
                for warning in estimation.warnings:
                    st.caption(f"• {warning}")

            st.caption(f"估算时间: {estimation.timestamp.strftime('%H:%M:%S')}")
        else:
            st.info("暂无持仓数据，无法估算")
        st.markdown('</div>', unsafe_allow_html=True)

    # Right column - Holdings table
    with col_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📊 前十大重仓股</div>', unsafe_allow_html=True)

        if holdings:
            table_data = []
            for holding in holdings:
                stock_code = holding.stock_code
                change_pct = quotes_dict[stock_code].change_pct if stock_code in quotes_dict else None

                if change_pct is not None:
                    # Chinese colors: red for gains, green for losses
                    change_color = "🔴" if change_pct > 0 else "🟢" if change_pct < 0 else "⚪"
                    change_str = f"{change_color} {change_pct:+.2f}%"
                else:
                    change_str = "N/A"

                table_data.append({
                    "排名": holding.rank,
                    "代码": stock_code,
                    "名称": holding.stock_name,
                    "占比": f"{holding.weight:.2f}%",
                    "涨跌": change_str
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)

            total_weight = sum(h.weight for h in holdings)
            st.caption(f"合计占比: {total_weight:.2f}%")
        else:
            st.info("暂无持仓数据")
        st.markdown('</div>', unsafe_allow_html=True)
