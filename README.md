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
