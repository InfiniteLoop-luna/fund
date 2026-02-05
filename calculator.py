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
