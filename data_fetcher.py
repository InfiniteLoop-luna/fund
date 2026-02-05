import tushare as ts
import streamlit as st
import pandas as pd
import requests
from typing import Optional, Tuple, List, Any
from models import FundBasicInfo, Holding, Quote, CachedData
from datetime import datetime


class TushareClient:
    """Client for fetching fund data from Tushare API"""

    def __init__(self):
        """Initialize Tushare client with token from secrets"""
        try:
            token = st.secrets["tushare"]["token"]
            ts.set_token(token)
            self.pro = ts.pro_api()
        except Exception as e:
            raise ValueError(f"Failed to initialize Tushare: {e}")

    def get_fund_basic(self, fund_code: str) -> Tuple[Optional[FundBasicInfo], Optional[str]]:
        """
        Fetch fund basic information

        Returns:
            (FundBasicInfo, None) on success
            (None, error_message) on failure
        """
        try:
            # Validate input
            if not fund_code or not fund_code.strip():
                return None, "Fund code cannot be empty"

            # Normalize fund code
            fund_code = fund_code.strip()
            if not fund_code.upper().endswith('.OF'):
                fund_code = f"{fund_code}.OF"

            # Fetch fund basic info
            df = self.pro.fund_basic(ts_code=fund_code, fields='ts_code,name,management,manager,found_date')

            if df.empty:
                return None, f"Fund code {fund_code} not found"

            # Validate required fields exist
            required_fields = ['ts_code', 'name', 'management', 'manager', 'found_date']
            missing_fields = [field for field in required_fields if field not in df.columns]
            if missing_fields:
                return None, f"Missing required fields in fund_basic response: {', '.join(missing_fields)}"

            # Fetch latest net value
            nav_df = self.pro.fund_nav(ts_code=fund_code, fields='end_date,unit_nav')

            if nav_df.empty:
                return None, f"No net value data found for {fund_code}"

            # Validate required fields exist in nav_df
            nav_required_fields = ['end_date', 'unit_nav']
            nav_missing_fields = [field for field in nav_required_fields if field not in nav_df.columns]
            if nav_missing_fields:
                return None, f"Missing required fields in fund_nav response: {', '.join(nav_missing_fields)}"

            # Get latest record
            nav_df = nav_df.sort_values('end_date', ascending=False).iloc[0]

            # Validate and convert net value
            unit_nav = nav_df['unit_nav']
            if pd.isna(unit_nav):
                return None, f"Net value is null for {fund_code}"

            try:
                net_value = float(unit_nav)
            except (ValueError, TypeError):
                return None, f"Invalid net value format: {unit_nav}"

            fund_info = FundBasicInfo(
                fund_code=df.iloc[0]['ts_code'],
                fund_name=df.iloc[0]['name'],
                management=df.iloc[0]['management'],
                manager=df.iloc[0]['manager'] if pd.notna(df.iloc[0]['manager']) else 'N/A',
                found_date=df.iloc[0]['found_date'],
                net_value=net_value,
                net_value_date=nav_df['end_date']
            )

            return fund_info, None

        except Exception as e:
            return None, f"Error fetching fund basic info: {str(e)}"

    def get_fund_portfolio(self, fund_code: str) -> Tuple[Optional[List[Holding]], Optional[str]]:
        """
        Fetch fund top 10 holdings

        Returns:
            (List[Holding], None) on success
            (None, error_message) on failure
        """
        try:
            # Validate input
            if not fund_code or not fund_code.strip():
                return None, "Fund code cannot be empty"

            # Normalize fund code
            fund_code = fund_code.strip()
            if not fund_code.upper().endswith('.OF'):
                fund_code = f"{fund_code}.OF"

            # Fetch portfolio (latest quarter)
            df = self.pro.fund_portfolio(ts_code=fund_code)

            if df.empty:
                return None, f"No holdings data found for {fund_code}"

            # Validate required fields exist
            required_fields = ['end_date', 'symbol', 'stk_name', 'mkv', 'stk_mkv_ratio']
            missing_fields = [field for field in required_fields if field not in df.columns]
            if missing_fields:
                return None, f"Missing required fields in fund_portfolio response: {', '.join(missing_fields)}"

            # Get latest quarter data
            latest_date = df['end_date'].max()
            df = df[df['end_date'] == latest_date]

            # Sort by weight and take top 10
            df = df.sort_values('mkv', ascending=False).head(10)

            holdings = []
            for idx, row in df.iterrows():
                # Validate and convert weight
                weight_value = row['stk_mkv_ratio']
                if pd.isna(weight_value):
                    continue  # Skip holdings with null weight

                try:
                    weight = float(weight_value)
                except (ValueError, TypeError):
                    continue  # Skip holdings with invalid weight format

                holding = Holding(
                    rank=len(holdings) + 1,
                    stock_code=row['symbol'],
                    stock_name=row['stk_name'],
                    weight=weight
                )
                holdings.append(holding)

            if not holdings:
                return None, f"No valid holdings data found for {fund_code}"

            return holdings, None

        except Exception as e:
            return None, f"Error fetching fund portfolio: {str(e)}"


class RealtimeQuoteClient:
    """Client for fetching real-time stock quotes with fallback"""

    def __init__(self, tushare_pro=None):
        self.pro = tushare_pro

    def get_realtime_quotes(self, stock_codes: List[str]) -> Tuple[dict, Optional[str]]:
        quotes, error = self._fetch_from_tushare(stock_codes)
        if quotes:
            return quotes, error
        quotes, error = self._fetch_from_sina(stock_codes)
        return quotes, error

    def _fetch_from_tushare(self, stock_codes: List[str]) -> Tuple[dict, Optional[str]]:
        if not self.pro:
            return {}, "Tushare API not available"
        try:
            ts_codes = [f"{code}.SH" if code.startswith('6') else f"{code}.SZ" for code in stock_codes]
            df = self.pro.daily(ts_code=','.join(ts_codes), fields='ts_code,trade_date,close,pct_chg')
            if df.empty:
                return {}, "No data from Tushare"
            df = df.sort_values('trade_date', ascending=False).drop_duplicates(subset=['ts_code'], keep='first')
            quotes = {}
            for _, row in df.iterrows():
                # Validate and convert close price
                close_value = row['close']
                if pd.isna(close_value):
                    continue  # Skip quotes with null close price

                try:
                    current_price = float(close_value)
                except (ValueError, TypeError):
                    continue  # Skip quotes with invalid close price format

                # Validate and convert pct_chg
                pct_chg_value = row['pct_chg']
                if pd.isna(pct_chg_value):
                    continue  # Skip quotes with null pct_chg

                try:
                    change_pct = float(pct_chg_value)
                except (ValueError, TypeError):
                    continue  # Skip quotes with invalid pct_chg format

                stock_code = row['ts_code'].split('.')[0]
                quotes[stock_code] = Quote(
                    stock_code=stock_code,
                    current_price=current_price,
                    change_pct=change_pct,
                    timestamp=datetime.now()
                )
            return quotes, None
        except Exception as e:
            return {}, f"Tushare error: {str(e)}"

    def _fetch_from_sina(self, stock_codes: List[str]) -> Tuple[dict, Optional[str]]:
        try:
            sina_codes = [f"sh{code}" if code.startswith('6') else f"sz{code}" for code in stock_codes]
            url = f"http://hq.sinajs.cn/list={','.join(sina_codes)}"
            response = requests.get(url, timeout=5)
            response.encoding = 'gbk'
            if response.status_code != 200:
                return {}, f"Sina API error: HTTP {response.status_code}"
            quotes = {}
            for line in response.text.strip().split('\n'):
                if '=' not in line:
                    continue

                # Add try-except around array indexing to handle malformed lines
                try:
                    code_part = line.split('=')[0].split('_')[-1]
                    data_part = line.split('"')[1]
                except IndexError:
                    continue  # Skip malformed lines

                if not data_part:
                    continue
                fields = data_part.split(',')
                if len(fields) < 4:
                    continue

                # Validate fields exist before accessing them
                if not code_part or len(code_part) < 3:
                    continue

                stock_code = code_part[2:]

                # Add try-except around float conversions to handle invalid data
                try:
                    current_price = float(fields[3])
                    prev_close = float(fields[2])
                except (ValueError, TypeError, IndexError):
                    continue  # Skip lines with invalid numeric data

                change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                quotes[stock_code] = Quote(
                    stock_code=stock_code,
                    current_price=current_price,
                    change_pct=change_pct,
                    timestamp=datetime.now()
                )
            return quotes, None if quotes else "No data from Sina"
        except Exception as e:
            return {}, f"Sina API error: {str(e)}"


class CacheManager:
    """Manages caching of fund data in session state"""
    FUND_INFO_TTL = 300
    QUOTES_TTL = 30

    @staticmethod
    def get_cached(key: str, ttl: int) -> Optional[CachedData]:
        if key not in st.session_state:
            return None
        cached = st.session_state[key]
        age = (datetime.now() - cached.timestamp).total_seconds()
        if age > ttl:
            cached.is_stale = True
        return cached

    @staticmethod
    def set_cached(key: str, data: Any):
        st.session_state[key] = CachedData(
            data=data,
            timestamp=datetime.now(),
            is_stale=False
        )

    @staticmethod
    def clear_cache():
        keys_to_remove = [k for k in st.session_state.keys() if k.startswith('cache_')]
        for key in keys_to_remove:
            del st.session_state[key]
