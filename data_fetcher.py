import tushare as ts
import streamlit as st
import pandas as pd
from typing import Optional, Tuple, List
from models import FundBasicInfo, Holding
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
