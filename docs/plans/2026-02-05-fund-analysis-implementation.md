# Fund Analysis App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Streamlit web app that displays fund information and estimates real-time net value using weighted holdings.

**Architecture:** Three-layer design with data fetching (Tushare + fallback), business logic (net value calculator), and UI (Streamlit). Uses session state for caching and graceful degradation on errors.

**Tech Stack:** Python 3.9+, Streamlit, Tushare, Pandas, Requests

---

## Task 1: Project Setup and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `.streamlit/config.toml`

**Step 1: Create requirements.txt**

Create file with dependencies:

```txt
streamlit>=1.30.0
tushare>=1.2.89
pandas>=2.0.0
requests>=2.31.0
```

**Step 2: Create README.md**

```markdown
# Fund Real-time Valuation Analysis Tool

A Streamlit web application for analyzing Chinese mutual funds with real-time net value estimation.

## Features
- Fund basic information display
- Top 10 holdings visualization
- Real-time net value estimation based on weighted holdings
- Configurable auto-refresh
- Graceful error handling with cached data

## Setup

### Local Development
1. Clone the repository
2. Create `.streamlit/secrets.toml`:
   ```toml
   [tushare]
   token = "your_tushare_token_here"
   ```
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`

### Streamlit Cloud Deployment
1. Push code to GitHub (`.streamlit/` is gitignored)
2. Connect repository to Streamlit Cloud
3. Add secrets in App Settings → Secrets:
   ```toml
   [tushare]
   token = "your_token_here"
   ```
4. Deploy

## Usage
1. Enter fund code (e.g., 000001.OF)
2. Click "查询" to fetch data
3. View fund info, holdings, and estimated net value
4. Configure auto-refresh in sidebar

## Architecture
- `app.py`: Main Streamlit UI
- `data_fetcher.py`: Data layer (Tushare + fallback)
- `calculator.py`: Business logic (net value estimation)
```

**Step 3: Create Streamlit config**

Create `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
headless = true
```

**Step 4: Install dependencies locally**

Run: `pip install -r requirements.txt`
Expected: All packages installed successfully

**Step 5: Commit**

```bash
git add requirements.txt README.md .streamlit/config.toml
git commit -m "feat: add project setup and dependencies"
```

---

## Task 2: Data Models and Type Definitions

**Files:**
- Create: `models.py`

**Step 1: Create data models**

Create `models.py` with dataclasses:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class FundBasicInfo:
    """Fund basic information"""
    fund_code: str
    fund_name: str
    management: str
    manager: str
    found_date: str
    net_value: float
    net_value_date: str


@dataclass
class Holding:
    """Stock holding information"""
    rank: int
    stock_code: str
    stock_name: str
    weight: float  # Percentage (e.g., 10.5 for 10.5%)


@dataclass
class Quote:
    """Real-time stock quote"""
    stock_code: str
    current_price: float
    change_pct: float  # Percentage (e.g., 2.5 for +2.5%)
    timestamp: datetime


@dataclass
class EstimationResult:
    """Net value estimation result"""
    estimated_value: float
    estimated_change_pct: float
    last_net_value: float
    coverage_pct: float  # Percentage of holdings with quotes
    confidence: str  # "high", "medium", "low"
    warnings: List[str]
    timestamp: datetime
    is_market_open: bool


@dataclass
class CachedData:
    """Cached data with timestamp"""
    data: any
    timestamp: datetime
    is_stale: bool = False
```

**Step 2: Commit**

```bash
git add models.py
git commit -m "feat: add data models and type definitions"
```

---

## Task 3: Data Fetcher - Tushare Client

**Files:**
- Create: `data_fetcher.py`

**Step 1: Create TushareClient class skeleton**

Create `data_fetcher.py`:

```python
import tushare as ts
import streamlit as st
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
        pass

    def get_fund_portfolio(self, fund_code: str) -> Tuple[Optional[List[Holding]], Optional[str]]:
        """
        Fetch fund top 10 holdings

        Returns:
            (List[Holding], None) on success
            (None, error_message) on failure
        """
        pass
```

**Step 2: Implement get_fund_basic method**

Add implementation:

```python
def get_fund_basic(self, fund_code: str) -> Tuple[Optional[FundBasicInfo], Optional[str]]:
    """
    Fetch fund basic information

    Returns:
        (FundBasicInfo, None) on success
        (None, error_message) on failure
    """
    try:
        # Normalize fund code
        if not fund_code.upper().endswith('.OF'):
            fund_code = f"{fund_code}.OF"

        # Fetch fund basic info
        df = self.pro.fund_basic(ts_code=fund_code, fields='ts_code,name,management,manager,found_date')

        if df.empty:
            return None, f"Fund code {fund_code} not found"

        # Fetch latest net value
        nav_df = self.pro.fund_nav(ts_code=fund_code, fields='end_date,unit_nav')

        if nav_df.empty:
            return None, f"No net value data found for {fund_code}"

        # Get latest record
        nav_df = nav_df.sort_values('end_date', ascending=False').iloc[0]

        fund_info = FundBasicInfo(
            fund_code=df.iloc[0]['ts_code'],
            fund_name=df.iloc[0]['name'],
            management=df.iloc[0]['management'],
            manager=df.iloc[0]['manager'] if df.iloc[0]['manager'] else 'N/A',
            found_date=df.iloc[0]['found_date'],
            net_value=float(nav_df['unit_nav']),
            net_value_date=nav_df['end_date']
        )

        return fund_info, None

    except Exception as e:
        return None, f"Error fetching fund basic info: {str(e)}"
```

**Step 3: Implement get_fund_portfolio method**

Add implementation:

```python
def get_fund_portfolio(self, fund_code: str) -> Tuple[Optional[List[Holding]], Optional[str]]:
    """
    Fetch fund top 10 holdings

    Returns:
        (List[Holding], None) on success
        (None, error_message) on failure
    """
    try:
        # Normalize fund code
        if not fund_code.upper().endswith('.OF'):
            fund_code = f"{fund_code}.OF"

        # Fetch portfolio (latest quarter)
        df = self.pro.fund_portfolio(ts_code=fund_code)

        if df.empty:
            return None, f"No holdings data found for {fund_code}"

        # Get latest quarter data
        latest_date = df['end_date'].max()
        df = df[df['end_date'] == latest_date]

        # Sort by weight and take top 10
        df = df.sort_values('mkv', ascending=False).head(10)

        holdings = []
        for idx, row in df.iterrows():
            holding = Holding(
                rank=len(holdings) + 1,
                stock_code=row['symbol'],
                stock_name=row['stk_name'],
                weight=float(row['stk_mkv_ratio'])
            )
            holdings.append(holding)

        return holdings, None

    except Exception as e:
        return None, f"Error fetching fund portfolio: {str(e)}"
```

**Step 4: Commit**

```bash
git add data_fetcher.py
git commit -m "feat: add Tushare client for fund data"
```

---

## Task 4: Data Fetcher - Real-time Quote Client

**Files:**
- Modify: `data_fetcher.py`

**Step 1: Add RealtimeQuoteClient class with Tushare method**

```python
import requests
from models import Quote


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
                stock_code = row['ts_code'].split('.')[0]
                quotes[stock_code] = Quote(
                    stock_code=stock_code,
                    current_price=float(row['close']),
                    change_pct=float(row['pct_chg']),
                    timestamp=datetime.now()
                )
            return quotes, None
        except Exception as e:
            return {}, f"Tushare error: {str(e)}"
```

**Step 2: Add Sina fallback method**

```python
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
                code_part = line.split('=')[0].split('_')[-1]
                data_part = line.split('"')[1]
                if not data_part:
                    continue
                fields = data_part.split(',')
                if len(fields) < 4:
                    continue
                stock_code = code_part[2:]
                current_price = float(fields[3])
                prev_close = float(fields[2])
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
```

**Step 3: Commit**

```bash
git add data_fetcher.py
git commit -m "feat: add real-time quote client with Sina fallback"
```

---

## Task 5: Cache Manager

**Files:**
- Modify: `data_fetcher.py`

**Step 1: Add CacheManager class**

```python
from models import CachedData


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
    def set_cached(key: str, data: any):
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
```

**Step 2: Commit**

```bash
git add data_fetcher.py
git commit -m "feat: add cache manager for session state"
```

---

## Task 6: Net Value Calculator

**Files:**
- Create: `calculator.py`

**Step 1: Create NetValueEstimator class**

```python
from typing import List, Dict
from models import Holding, Quote, EstimationResult
from datetime import datetime, time


class NetValueEstimator:
    """Calculates estimated net value based on holdings and real-time quotes"""

    @staticmethod
    def is_market_open() -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        market_open = time(9, 30)
        market_close = time(15, 0)
        return market_open <= now.time() <= market_close

    @staticmethod
    def calculate_estimated_value(
        last_net_value: float,
        holdings: List[Holding],
        realtime_quotes: Dict[str, Quote]
    ) -> EstimationResult:
        warnings = []
        weighted_change = 0.0
        holdings_with_quotes = 0

        for holding in holdings:
            if holding.stock_code in realtime_quotes:
                quote = realtime_quotes[holding.stock_code]
                if abs(quote.change_pct) > 10:
                    warnings.append(f"{holding.stock_name} has extreme change: {quote.change_pct:+.2f}%")
                weight_decimal = holding.weight / 100
                weighted_change += weight_decimal * (quote.change_pct / 100)
                holdings_with_quotes += 1

        coverage_pct = (holdings_with_quotes / len(holdings)) * 100 if holdings else 0
        confidence = "high" if coverage_pct >= 80 else "medium" if coverage_pct >= 60 else "low"

        if coverage_pct < 60:
            warnings.append(f"Low coverage: only {holdings_with_quotes}/{len(holdings)} holdings have quotes")

        estimated_change_pct = weighted_change * 100
        if abs(estimated_change_pct) > 5:
            warnings.append(f"Extreme total change: {estimated_change_pct:+.2f}% (possible data error)")

        estimated_value = last_net_value * (1 + weighted_change)
        is_market_open = NetValueEstimator.is_market_open()

        if not is_market_open:
            warnings.append("Market is closed. Showing last available data.")

        return EstimationResult(
            estimated_value=estimated_value,
            estimated_change_pct=estimated_change_pct,
            last_net_value=last_net_value,
            coverage_pct=coverage_pct,
            confidence=confidence,
            warnings=warnings,
            timestamp=datetime.now(),
            is_market_open=is_market_open
        )
```

**Step 2: Commit**

```bash
git add calculator.py
git commit -m "feat: add net value estimator with market hours check"
```

---

