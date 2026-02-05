import streamlit as st
import time
from datetime import datetime
from data_fetcher import TushareClient, RealtimeQuoteClient, CacheManager
from calculator import NetValueEstimator

# Page config
st.set_page_config(
    page_title="基金实时估值分析工具",
    page_icon="📈",
    layout="wide"
)

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'fund_code' not in st.session_state:
    st.session_state.fund_code = ""

# Sidebar with refresh controls
with st.sidebar:
    st.title("⚙️ 设置")

    # Fund list search section
    st.subheader("📋 基金列表")

    # Load fund list (cached)
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

    fund_list_df, fund_list_error = load_fund_list()

    if fund_list_error:
        st.error(f"加载基金列表失败: {fund_list_error}")
    elif fund_list_df is not None:
        # Search box
        search_term = st.text_input(
            "搜索基金",
            placeholder="输入基金代码或名称",
            help="支持模糊搜索基金代码或名称"
        )

        # Filter funds based on search term
        if search_term:
            filtered_df = fund_list_df[
                fund_list_df['ts_code'].str.contains(search_term, case=False, na=False) |
                fund_list_df['name'].str.contains(search_term, case=False, na=False)
            ].head(50)  # Limit to 50 results for performance
        else:
            filtered_df = fund_list_df.head(50)  # Show first 50 by default

        # Display fund count
        if search_term:
            st.caption(f"找到 {len(fund_list_df[fund_list_df['ts_code'].str.contains(search_term, case=False, na=False) | fund_list_df['name'].str.contains(search_term, case=False, na=False)])} 个基金，显示前 {len(filtered_df)} 个")
        else:
            st.caption(f"共 {len(fund_list_df)} 个基金，显示前 {len(filtered_df)} 个")

        # Fund selection
        if not filtered_df.empty:
            # Create display options: "代码 - 名称"
            fund_options = [f"{row['ts_code'].replace('.OF', '')} - {row['name']}"
                          for _, row in filtered_df.iterrows()]

            selected_fund = st.selectbox(
                "选择基金",
                options=[""] + fund_options,
                format_func=lambda x: "请选择..." if x == "" else x
            )

            if selected_fund and selected_fund != "":
                # Extract fund code from selection
                selected_code = selected_fund.split(" - ")[0]
                if st.button("📊 查看该基金", use_container_width=True, type="primary"):
                    st.session_state.fund_code = selected_code
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
st.title("📈 基金实时估值分析工具")
st.markdown("---")

# Input section
col1, col2 = st.columns([3, 1])
with col1:
    fund_code_input = st.text_input(
        "基金代码",
        value=st.session_state.fund_code,
        placeholder="请输入6位基金代码，如: 000001",
        help="输入基金代码，支持格式: 000001 或 000001.OF"
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    query_button = st.button("🔍 查询", use_container_width=True, type="primary")

if query_button and fund_code_input:
    st.session_state.fund_code = fund_code_input.strip()
    CacheManager.clear_cache()

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

    # Display results in three columns
    st.markdown("---")
    col_left, col_center, col_right = st.columns([1, 1, 1])

    # Left column - Fund basic info
    with col_left:
        st.subheader("📋 基金信息")
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

    # Center column - Real-time estimation
    with col_center:
        st.subheader("💹 实时估值")

        if estimation:
            # Market status
            if estimation.is_market_open:
                st.success("🟢 交易中")
            else:
                st.info("🔒 休市")

            # Estimated value
            change_color = "#FF4B4B" if estimation.estimated_change_pct > 0 else "#00C853" if estimation.estimated_change_pct < 0 else "#666666"

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

    # Right column - Holdings table
    with col_right:
        st.subheader("📊 前十大重仓股")

        if holdings:
            table_data = []
            for holding in holdings:
                stock_code = holding.stock_code
                change_pct = quotes_dict[stock_code].change_pct if stock_code in quotes_dict else None

                if change_pct is not None:
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
