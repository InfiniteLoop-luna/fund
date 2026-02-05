from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional


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
    data: Any
    timestamp: datetime
    is_stale: bool = False
