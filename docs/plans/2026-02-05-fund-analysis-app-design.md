# Fund Real-time Valuation Analysis Tool - Design Document

**Date:** 2026-02-05
**Status:** Approved
**Author:** Claude (Brainstorming Session)

## Overview

A Streamlit web application that provides real-time net value estimation for mutual funds in China. Users input a fund code, and the app displays fund basic information, top 10 holdings, and calculates estimated net value based on real-time stock price movements.

## Design Decisions

### 1. Data Source Strategy
- **Primary:** Tushare Pro API for fund basic info and holdings
- **Real-time Quotes:** Attempt Tushare first, fallback to web scraping (Sina Finance API)
- **Rationale:** Maximizes data quality while handling Tushare permission restrictions

### 2. Token Security
- **Method:** Streamlit Secrets (`.streamlit/secrets.toml`)
- **Deployment:** Secrets configured in Streamlit Cloud dashboard
- **Rationale:** Industry standard, secure, prevents token exposure in git

### 3. Refresh Strategy
- **Type:** Configurable auto-refresh (Manual, 15s, 30s, 60s)
- **Implementation:** `st.rerun()` with timer
- **Rationale:** Gives users control over data freshness vs. API usage

### 4. Error Handling
- **Strategy:** Graceful degradation with cached data
- **Features:** Show last successful data with timestamp, warning banners, retry buttons
- **Rationale:** Best user experience, keeps app functional during temporary failures

### 5. UI Layout
- **Type:** Balanced three-column layout
- **Columns:** Fund Info (left), Real-time Estimation (center), Holdings (right)
- **Rationale:** Equal visual weight to all key information

## Architecture

### Component Structure

```
fund/
├── app.py                 # Main Streamlit application
├── data_fetcher.py        # Data layer (Tushare + fallback)
├── calculator.py          # Business logic (estimation)
├── requirements.txt       # Dependencies
├── .gitignore            # Exclude secrets and cache
├── .streamlit/
│   └── secrets.toml      # Local secrets (gitignored)
├── docs/
│   └── plans/
│       └── 2026-02-05-fund-analysis-app-design.md
└── README.md             # Setup instructions
```

### Core Modules

#### 1. Data Layer (`data_fetcher.py`)

**TushareClient:**
- `get_fund_basic(fund_code)` → Returns fund name, manager, establishment date, latest net value
- `get_fund_portfolio(fund_code)` → Returns top 10 holdings with stock codes and weights
- Uses Tushare `fund_basic` and `fund_portfolio` APIs
- Error types: `NotFoundError`, `RateLimitError`, `NetworkError`

**RealtimeQuoteClient:**
- **Primary:** Attempt Tushare `daily` or `realtime_quote` API
- **Fallback:** Scrape Sina Finance API (`http://hq.sinajs.cn/list=`)
- Returns: stock code, current price, change percentage, timestamp
- Batch fetching for efficiency

**CacheManager:**
- Uses `st.session_state` for in-memory caching
- Stores: fund_info, holdings, last_quotes, timestamps
- TTL: 5 minutes for fund info, 30 seconds for quotes
- Method: `get_cached_or_fetch()` returns `(data, error, is_cached)`

#### 2. Business Logic (`calculator.py`)

**NetValueEstimator:**

```python
class NetValueEstimator:
    def calculate_estimated_value(
        last_net_value: float,
        holdings: List[Holding],
        realtime_quotes: Dict[str, Quote]
    ) -> EstimationResult
```

**Calculation Formula:**
```
Weighted Change = Σ(Stock_i Weight × Stock_i Real-time Change %)
Estimated Net Value = Last Net Value × (1 + Weighted Change)
```

**Example:**
- Last net value: 2.5000
- Stock A: 10% weight, +2.5% change → 0.10 × 0.025 = 0.0025
- Stock B: 8% weight, -1.2% change → 0.08 × (-0.012) = -0.00096
- Total weighted change: +1.5%
- Estimated value: 2.5000 × 1.015 = 2.5375

**Edge Cases:**
- Partial data: Calculate with available holdings, flag low confidence
- Market closed: Return last net value with indicator
- Suspended stocks: Treat as 0% change
- Extreme changes: Flag if single stock >10% or total >5%

**Output Structure:**
```python
EstimationResult(
    estimated_value: float,
    estimated_change_pct: float,
    last_net_value: float,
    coverage_pct: float,  # % of holdings with quotes
    confidence: str,  # "high", "medium", "low"
    warnings: List[str],
    timestamp: datetime
)
```

#### 3. UI Layer (`app.py`)

**Header Section:**
- App title: "基金实时估值分析工具"
- Sidebar refresh controls:
  - Refresh interval selector (Manual, 15s, 30s, 60s)
  - Manual refresh button
  - Auto-refresh countdown
  - Last update timestamp

**Three-Column Layout:**

**Left Column - Fund Basic Info:**
- Fund name (large, bold)
- Fund code (smaller, gray)
- Management company
- Fund manager name
- Establishment date
- Last published net value with date
- Data staleness indicator

**Center Column - Real-time Estimation:**
- Large estimated net value (2x font size)
- Color-coded change percentage:
  - Red (#FF4B4B) for positive
  - Green (#00C853) for negative
  - Gray for 0% or market closed
- Confidence indicator with tooltip
- Coverage percentage
- Market status badge
- Timestamp

**Right Column - Top 10 Holdings:**
- Sortable table: Rank, Code, Name, Weight %, Change %
- Color-coded changes
- Total coverage at bottom
- Missing data indicators

## Data Flow

```
User Input (Fund Code)
    ↓
Validate & Normalize Input
    ↓
Fetch Fund Basic Info (Tushare) ──→ Cache
    ↓
Fetch Fund Holdings (Tushare) ──→ Cache
    ↓
Fetch Real-time Quotes (Tushare/Fallback) ──→ Cache
    ↓
Calculate Estimated Net Value
    ↓
Display Results (with cached fallback on errors)
```

## Error Handling

### Graceful Degradation Scenarios

**API Rate Limit:**
- Display cached data with warning: "⚠️ Using cached data from [timestamp]"
- Show retry button
- Auto-retry after 60s

**Fund Not Found:**
- Clear error: "❌ Fund code [XXX] not found"
- Suggest format: "6 digits + .OF (e.g., 000001.OF)"
- No cached data

**Partial Holdings:**
- Calculate with available data
- Warning: "⚠️ Estimation based on 7/10 holdings (70% coverage)"
- Low confidence if coverage < 60%

**Market Closed:**
- Display last net value only
- Badge: "🔒 Market Closed"
- Disable auto-refresh
- Show market hours: "9:30-15:00"

**Network Timeout:**
- Show cached data with timestamp
- Display: "⚠️ Network timeout. Showing last data from [timestamp]"
- Retry button

**Tushare Permission Denied:**
- Auto-fallback to web scraping
- Log event (silent to user)
- Continue normal operation

### Input Validation

- Accept formats: "000001", "000001.OF", "000001.of"
- Normalize to uppercase with .OF suffix
- Trim whitespace
- Reject invalid with helpful message

## Configuration

### Dependencies (`requirements.txt`)
```
streamlit>=1.30.0
tushare>=1.2.89
pandas>=2.0.0
requests>=2.31.0
```

### Secrets (`.streamlit/secrets.toml`)
```toml
[tushare]
token = "your_tushare_token_here"
```

### Gitignore (`.gitignore`)
```
.streamlit/
__pycache__/
*.pyc
.env
.vscode/
```

## Deployment

### Streamlit Cloud Setup

1. **Prepare Repository:**
   - Push code to GitHub (exclude `.streamlit/`)
   - Ensure `.gitignore` is configured

2. **Connect to Streamlit Cloud:**
   - Link GitHub repository
   - Select `app.py` as main file

3. **Configure Secrets:**
   - Go to App Settings → Secrets
   - Add Tushare token:
     ```toml
     [tushare]
     token = "your_token_here"
     ```

4. **Deploy:**
   - Automatic deployment on push
   - Monitor logs for errors

### Local Development

1. Clone repository
2. Create `.streamlit/secrets.toml` with token
3. Install: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`

## Technical Considerations

### Performance
- Batch fetch all 10 stock quotes in single request
- Cache fund info for 5 minutes (rarely changes)
- Cache quotes for 30 seconds (balance freshness vs. API calls)
- Use `st.session_state` for in-memory caching

### Accuracy
- Top 10 holdings typically represent 40-60% of portfolio
- Estimation accuracy depends on holdings coverage
- Focus on equity funds (bond funds need different logic)
- Valid only during trading hours (9:30-15:00)

### API Limits
- Tushare free tier: 200 calls/minute
- Implement exponential backoff on rate limits
- Fallback to web scraping reduces API dependency
- Cache aggressively to minimize calls

### Security
- Never commit `.streamlit/secrets.toml`
- Use Streamlit Cloud secrets for production
- No hardcoded tokens in code
- Validate all user inputs

## Future Enhancements (Out of Scope)

- Historical estimation accuracy tracking
- Multiple fund comparison
- Alert notifications for significant changes
- Export data to CSV/Excel
- Support for bond and money market funds
- Mobile-responsive design improvements

## Success Criteria

- ✅ User can input fund code and view basic info
- ✅ Top 10 holdings displayed with real-time changes
- ✅ Estimated net value calculated and displayed
- ✅ Configurable auto-refresh works correctly
- ✅ Graceful degradation on API errors
- ✅ Secure token management for deployment
- ✅ Clean, balanced three-column UI
- ✅ Color-coded changes (red/green)

## Conclusion

This design provides a robust, user-friendly fund analysis tool with real-time estimation capabilities. The graceful degradation strategy ensures reliability, while the configurable refresh and balanced layout optimize user experience. The fallback data source strategy handles Tushare permission restrictions effectively.
