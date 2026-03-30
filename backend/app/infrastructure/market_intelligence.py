"""
Market intelligence integration for economic calendar, social sentiment, and earnings data.
"""

import logging
import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import re
from textblob import TextBlob
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class EventImpact(Enum):
    """Economic event impact levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class EventType(Enum):
    """Types of economic events."""
    INTEREST_RATE = "interest_rate"
    INFLATION = "inflation"
    EMPLOYMENT = "employment"
    GDP = "gdp"
    RETAIL_SALES = "retail_sales"
    MANUFACTURING = "manufacturing"
    HOUSING = "housing"
    CONSUMER_CONFIDENCE = "consumer_confidence"
    TRADE_BALANCE = "trade_balance"
    CENTRAL_BANK = "central_bank"


class SentimentSource(Enum):
    """Social media sentiment sources."""
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"


@dataclass
class EconomicEvent:
    """Economic calendar event."""
    event_id: str
    title: str
    country: str
    currency: str
    event_type: EventType
    date: datetime
    actual: Optional[float]
    forecast: Optional[float]
    previous: Optional[float]
    impact: EventImpact
    importance: int  # 1-5 scale
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['impact'] = self.impact.value
        result['date'] = self.date.isoformat()
        return result


@dataclass
class SentimentData:
    """Social sentiment data."""
    source: SentimentSource
    symbol: str
    timestamp: datetime
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1
    volume: int  # Number of mentions
    text_sample: str
    keywords: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['source'] = self.source.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class EarningsData:
    """Earnings calendar data."""
    symbol: str
    company_name: str
    earnings_date: datetime
    quarter: int
    year: int
    eps_actual: Optional[float]
    eps_forecast: Optional[float]
    eps_previous: Optional[float]
    revenue_actual: Optional[float]
    revenue_forecast: Optional[float]
    revenue_previous: Optional[float]
    surprise_percent: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['earnings_date'] = self.earnings_date.isoformat()
        return result


class EconomicCalendar(LoggerMixin):
    """Economic calendar integration."""
    
    def __init__(self, api_key: str = None):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.api_key = api_key or os.environ.get('ECONOMIC_CALENDAR_API_KEY')
        self.base_url = "https://api.economic-calendar.com/v1"
    
    async def get_economic_events(self, start_date: datetime, end_date: datetime,
                                 countries: List[str] = None, 
                                 impact_levels: List[EventImpact] = None) -> List[EconomicEvent]:
        """Get economic events for date range."""
        try:
            cache_key = f"economic_events:{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}"
            
            # Check cache first
            cached_events = self.cache.get(cache_key)
            if cached_events:
                return [EconomicEvent(**event) for event in cached_events]
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                params = {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "api_key": self.api_key
                }
                
                if countries:
                    params["countries"] = ",".join(countries)
                
                if impact_levels:
                    params["impact"] = ",".join([level.value for level in impact_levels])
                
                async with session.get(f"{self.base_url}/events", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        events = []
                        
                        for event_data in data.get("events", []):
                            event = EconomicEvent(
                                event_id=event_data["id"],
                                title=event_data["title"],
                                country=event_data["country"],
                                currency=event_data["currency"],
                                event_type=EventType(event_data["type"]),
                                date=datetime.fromisoformat(event_data["date"]),
                                actual=event_data.get("actual"),
                                forecast=event_data.get("forecast"),
                                previous=event_data.get("previous"),
                                impact=EventImpact(event_data["impact"]),
                                importance=event_data.get("importance", 3),
                                description=event_data.get("description", "")
                            )
                            events.append(event)
                        
                        # Cache results
                        self.cache.set(cache_key, [event.to_dict() for event in events], ttl=3600)  # 1 hour
                        
                        self.logger.info(f"Retrieved {len(events)} economic events")
                        
                        # Record metrics
                        self.metrics.record_trading_signal(
                            signal_type="economic_events_retrieved",
                            asset_symbol=str(len(events))
                        )
                        
                        return events
                    else:
                        self.logger.error(f"Error fetching economic events: {response.status}")
                        return []
            
        except Exception as e:
            self.logger.error(f"Error getting economic events: {e}")
            return []
    
    async def get_upcoming_events(self, days: int = 7, countries: List[str] = None) -> List[EconomicEvent]:
        """Get upcoming economic events."""
        try:
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=days)
            
            return await self.get_economic_events(start_date, end_date, countries)
            
        except Exception as e:
            self.logger.error(f"Error getting upcoming events: {e}")
            return []
    
    def analyze_market_impact(self, events: List[EconomicEvent]) -> Dict[str, Any]:
        """Analyze potential market impact of economic events."""
        try:
            if not events:
                return {"total_events": 0, "high_impact_events": 0, "analysis": "No events to analyze"}
            
            # Group events by impact
            high_impact_events = [e for e in events if e.impact in [EventImpact.HIGH, EventImpact.EXTREME]]
            medium_impact_events = [e for e in events if e.impact == EventImpact.MEDIUM]
            low_impact_events = [e for e in events if e.impact == EventImpact.LOW]
            
            # Group by event type
            events_by_type = {}
            for event in events:
                event_type = event.event_type.value
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)
            
            # Group by country
            events_by_country = {}
            for event in events:
                country = event.country
                if country not in events_by_country:
                    events_by_country[country] = []
                events_by_country[country].append(event)
            
            # Calculate impact score
            impact_score = 0
            for event in events:
                if event.impact == EventImpact.EXTREME:
                    impact_score += 5
                elif event.impact == EventImpact.HIGH:
                    impact_score += 3
                elif event.impact == EventImpact.MEDIUM:
                    impact_score += 2
                elif event.impact == EventImpact.LOW:
                    impact_score += 1
            
            # Generate recommendations
            recommendations = self._generate_economic_recommendations(events)
            
            return {
                "total_events": len(events),
                "high_impact_events": len(high_impact_events),
                "medium_impact_events": len(medium_impact_events),
                "low_impact_events": len(low_impact_events),
                "impact_score": impact_score,
                "events_by_type": {k: len(v) for k, v in events_by_type.items()},
                "events_by_country": {k: len(v) for k, v in events_by_country.items()},
                "upcoming_high_impact": [
                    {
                        "title": event.title,
                        "date": event.date.isoformat(),
                        "country": event.country,
                        "forecast": event.forecast,
                        "previous": event.previous
                    }
                    for event in high_impact_events[:5]  # Top 5 upcoming
                ],
                "recommendations": recommendations,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing market impact: {e}")
            return {}


class SocialSentimentAnalyzer(LoggerMixin):
    """Social media sentiment analysis."""
    
    def __init__(self, twitter_api_key: str = None, reddit_api_key: str = None):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.twitter_api_key = twitter_api_key or os.environ.get('TWITTER_API_KEY')
        self.reddit_api_key = reddit_api_key or os.environ.get('REDDIT_API_KEY')
    
    async def analyze_twitter_sentiment(self, symbol: str, hours_back: int = 24) -> List[SentimentData]:
        """Analyze Twitter sentiment for a symbol."""
        try:
            cache_key = f"twitter_sentiment:{symbol}:{hours_back}"
            
            # Check cache first
            cached_sentiment = self.cache.get(cache_key)
            if cached_sentiment:
                return [SentimentData(**data) for data in cached_sentiment]
            
            # Mock implementation - in production, use Twitter API
            sentiment_data = await self._mock_twitter_sentiment(symbol, hours_back)
            
            # Cache results
            self.cache.set(cache_key, [data.to_dict() for data in sentiment_data], ttl=1800)  # 30 minutes
            
            self.logger.info(f"Analyzed Twitter sentiment for {symbol}")
            
            return sentiment_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing Twitter sentiment: {e}")
            return []
    
    async def analyze_reddit_sentiment(self, symbol: str, hours_back: int = 24) -> List[SentimentData]:
        """Analyze Reddit sentiment for a symbol."""
        try:
            cache_key = f"reddit_sentiment:{symbol}:{hours_back}"
            
            # Check cache first
            cached_sentiment = self.cache.get(cache_key)
            if cached_sentiment:
                return [SentimentData(**data) for data in cached_sentiment]
            
            # Mock implementation - in production, use Reddit API
            sentiment_data = await self._mock_reddit_sentiment(symbol, hours_back)
            
            # Cache results
            self.cache.set(cache_key, [data.to_dict() for data in sentiment_data], ttl=1800)  # 30 minutes
            
            self.logger.info(f"Analyzed Reddit sentiment for {symbol}")
            
            return sentiment_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing Reddit sentiment: {e}")
            return []
    
    async def _mock_twitter_sentiment(self, symbol: str, hours_back: int) -> List[SentimentData]:
        """Mock Twitter sentiment analysis."""
        try:
            # Generate mock sentiment data
            sentiment_data = []
            
            # Simulate multiple data points over time
            for i in range(hours_back):
                timestamp = datetime.utcnow() - timedelta(hours=i)
                
                # Random sentiment score between -0.3 and 0.7
                sentiment_score = np.random.normal(0.2, 0.3)
                sentiment_score = max(-1, min(1, sentiment_score))
                
                # Random confidence
                confidence = np.random.uniform(0.6, 0.95)
                
                # Random volume
                volume = np.random.randint(50, 500)
                
                # Mock text
                positive_texts = [
                    f"Great performance by {symbol} today!",
                    f"Bullish on {symbol}, strong fundamentals",
                    f"{symbol} showing strong momentum",
                    f"Long {symbol} for the long term"
                ]
                
                negative_texts = [
                    f"Concerned about {symbol} valuation",
                    f"{symbol} seems overbought",
                    f"Taking profits on {symbol}",
                    f"{symbol} facing headwinds"
                ]
                
                if sentiment_score > 0:
                    text = np.random.choice(positive_texts)
                else:
                    text = np.random.choice(negative_texts)
                
                # Extract keywords
                keywords = self._extract_keywords(text)
                
                sentiment = SentimentData(
                    source=SentimentSource.TWITTER,
                    symbol=symbol,
                    timestamp=timestamp,
                    sentiment_score=sentiment_score,
                    confidence=confidence,
                    volume=volume,
                    text_sample=text,
                    keywords=keywords
                )
                
                sentiment_data.append(sentiment)
            
            return sentiment_data
            
        except Exception as e:
            self.logger.error(f"Error in mock Twitter sentiment: {e}")
            return []
    
    async def _mock_reddit_sentiment(self, symbol: str, hours_back: int) -> List[SentimentData]:
        """Mock Reddit sentiment analysis."""
        try:
            # Generate mock sentiment data
            sentiment_data = []
            
            # Simulate fewer data points for Reddit (less frequent)
            for i in range(0, hours_back, 3):  # Every 3 hours
                timestamp = datetime.utcnow() - timedelta(hours=i)
                
                # Reddit sentiment tends to be more extreme
                sentiment_score = np.random.normal(0.1, 0.4)
                sentiment_score = max(-1, min(1, sentiment_score))
                
                confidence = np.random.uniform(0.7, 0.9)
                volume = np.random.randint(20, 200)
                
                # Mock Reddit text
                positive_texts = [
                    f"DD shows {symbol} has strong fundamentals",
                    f"Technical analysis suggests {symbol} is undervalued",
                    f"Long term holder of {symbol}, believe in the vision",
                    f"{symbol} earnings look promising"
                ]
                
                negative_texts = [
                    f"Concerned about {symbol} debt levels",
                    f"{symbol} growth slowing down?",
                    f"Market conditions affecting {symbol}",
                    f"{symbol} competition is heating up"
                ]
                
                if sentiment_score > 0:
                    text = np.random.choice(positive_texts)
                else:
                    text = np.random.choice(negative_texts)
                
                keywords = self._extract_keywords(text)
                
                sentiment = SentimentData(
                    source=SentimentSource.REDDIT,
                    symbol=symbol,
                    timestamp=timestamp,
                    sentiment_score=sentiment_score,
                    confidence=confidence,
                    volume=volume,
                    text_sample=text,
                    keywords=keywords
                )
                
                sentiment_data.append(sentiment)
            
            return sentiment_data
            
        except Exception as e:
            self.logger.error(f"Error in mock Reddit sentiment: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        try:
            # Simple keyword extraction
            words = re.findall(r'\b\w+\b', text.lower())
            
            # Filter out common words
            stop_words = {'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'as', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'shall'}
            
            keywords = [word for word in words if word not in stop_words and len(word) > 2]
            
            return list(set(keywords))  # Remove duplicates
            
        except Exception as e:
            self.logger.error(f"Error extracting keywords: {e}")
            return []
    
    def analyze_sentiment_trend(self, sentiment_data: List[SentimentData]) -> Dict[str, Any]:
        """Analyze sentiment trend over time."""
        try:
            if not sentiment_data:
                return {"error": "No sentiment data provided"}
            
            # Sort by timestamp
            sorted_data = sorted(sentiment_data, key=lambda x: x.timestamp)
            
            # Calculate weighted average sentiment
            total_weight = sum(data.volume * data.confidence for data in sorted_data)
            if total_weight > 0:
                weighted_sentiment = sum(data.sentiment_score * data.volume * data.confidence for data in sorted_data) / total_weight
            else:
                weighted_sentiment = 0
            
            # Calculate trend
            if len(sorted_data) >= 2:
                recent_sentiment = sorted_data[-1].sentiment_score
                older_sentiment = sorted_data[0].sentiment_score
                trend = recent_sentiment - older_sentiment
            else:
                trend = 0
            
            # Volume trend
            recent_volume = sum(data.volume for data in sorted_data[-5:]) if len(sorted_data) >= 5 else sum(data.volume for data in sorted_data)
            older_volume = sum(data.volume for data in sorted_data[:5]) if len(sorted_data) >= 5 else 0
            
            volume_trend = recent_volume - older_volume if older_volume > 0 else 0
            
            # Sentiment distribution
            positive_count = sum(1 for data in sorted_data if data.sentiment_score > 0.1)
            negative_count = sum(1 for data in sorted_data if data.sentiment_score < -0.1)
            neutral_count = len(sorted_data) - positive_count - negative_count
            
            return {
                "current_sentiment": weighted_sentiment,
                "sentiment_trend": trend,
                "volume_trend": volume_trend,
                "sentiment_distribution": {
                    "positive": positive_count,
                    "negative": negative_count,
                    "neutral": neutral_count
                },
                "average_confidence": sum(data.confidence for data in sorted_data) / len(sorted_data),
                "total_volume": sum(data.volume for data in sorted_data),
                "data_points": len(sorted_data),
                "latest_update": sorted_data[-1].timestamp.isoformat() if sorted_data else None
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment trend: {e}")
            return {}


class EarningsCalendar(LoggerMixin):
    """Earnings calendar integration."""
    
    def __init__(self, api_key: str = None):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.api_key = api_key or os.environ.get('EARNINGS_API_KEY')
        self.base_url = "https://api.earnings-calendar.com/v1"
    
    async def get_earnings_calendar(self, start_date: datetime, end_date: datetime,
                                  symbols: List[str] = None) -> List[EarningsData]:
        """Get earnings calendar for date range."""
        try:
            cache_key = f"earnings_calendar:{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}"
            
            # Check cache first
            cached_earnings = self.cache.get(cache_key)
            if cached_earnings:
                return [EarningsData(**earning) for earning in cached_earnings]
            
            # Mock implementation - in production, use earnings API
            earnings_data = await self._mock_earnings_data(start_date, end_date, symbols)
            
            # Cache results
            self.cache.set(cache_key, [earning.to_dict() for earning in earnings_data], ttl=3600)  # 1 hour
            
            self.logger.info(f"Retrieved {len(earnings_data)} earnings data")
            
            return earnings_data
            
        except Exception as e:
            self.logger.error(f"Error getting earnings calendar: {e}")
            return []
    
    async def _mock_earnings_data(self, start_date: datetime, end_date: datetime,
                                symbols: List[str] = None) -> List[EarningsData]:
        """Mock earnings data generation."""
        try:
            earnings_data = []
            
            # Generate mock earnings for common symbols
            common_symbols = symbols or ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM']
            
            current_date = start_date
            while current_date <= end_date:
                # Randomly select symbols for this date
                num_earnings = np.random.randint(1, 4)
                selected_symbols = np.random.choice(common_symbols, num_earnings, replace=False)
                
                for symbol in selected_symbols:
                    # Generate mock earnings data
                    quarter = (current_date.month - 1) // 3 + 1
                    year = current_date.year
                    
                    # Random EPS data
                    eps_forecast = np.random.uniform(0.5, 5.0)
                    eps_actual = eps_forecast * np.random.uniform(0.8, 1.3)
                    eps_previous = eps_forecast * np.random.uniform(0.9, 1.2)
                    
                    # Calculate surprise
                    surprise_percent = ((eps_actual - eps_forecast) / eps_forecast) * 100 if eps_forecast > 0 else 0
                    
                    # Random revenue data
                    revenue_forecast = np.random.uniform(1000, 50000)  # In millions
                    revenue_actual = revenue_forecast * np.random.uniform(0.9, 1.15)
                    revenue_previous = revenue_forecast * np.random.uniform(0.95, 1.1)
                    
                    earning = EarningsData(
                        symbol=symbol,
                        company_name=f"{symbol} Corporation",
                        earnings_date=current_date,
                        quarter=quarter,
                        year=year,
                        eps_actual=eps_actual,
                        eps_forecast=eps_forecast,
                        eps_previous=eps_previous,
                        revenue_actual=revenue_actual,
                        revenue_forecast=revenue_forecast,
                        revenue_previous=revenue_previous,
                        surprise_percent=surprise_percent
                    )
                    
                    earnings_data.append(earning)
                
                current_date += timedelta(days=1)
            
            return earnings_data
            
        except Exception as e:
            self.logger.error(f"Error generating mock earnings data: {e}")
            return []
    
    def analyze_earnings_impact(self, earnings_data: List[EarningsData]) -> Dict[str, Any]:
        """Analyze earnings impact on market."""
        try:
            if not earnings_data:
                return {"total_earnings": 0, "analysis": "No earnings data available"}
            
            # Calculate surprise statistics
            surprises = [earning.surprise_percent for earning in earnings_data if earning.surprise_percent is not None]
            
            if surprises:
                avg_surprise = np.mean(surprises)
                positive_surprises = len([s for s in surprises if s > 0])
                negative_surprises = len([s for s in surprises if s < 0])
            else:
                avg_surprise = 0
                positive_surprises = 0
                negative_surprises = 0
            
            # Group by quarter
            earnings_by_quarter = {}
            for earning in earnings_data:
                quarter_key = f"{earning.year}Q{earning.quarter}"
                if quarter_key not in earnings_by_quarter:
                    earnings_by_quarter[quarter_key] = []
                earnings_by_quarter[quarter_key].append(earning)
            
            # Find biggest surprises
            biggest_positive = max(earnings_data, key=lambda x: x.surprise_percent or 0) if earnings_data else None
            biggest_negative = min(earnings_data, key=lambda x: x.surprise_percent or 0) if earnings_data else None
            
            return {
                "total_earnings": len(earnings_data),
                "average_surprise": avg_surprise,
                "positive_surprises": positive_surprises,
                "negative_surprises": negative_surprises,
                "earnings_by_quarter": {k: len(v) for k, v in earnings_by_quarter.items()},
                "biggest_positive_surprise": {
                    "symbol": biggest_positive.symbol,
                    "surprise": biggest_positive.surprise_percent,
                    "date": biggest_positive.earnings_date.isoformat()
                } if biggest_positive else None,
                "biggest_negative_surprise": {
                    "symbol": biggest_negative.symbol,
                    "surprise": biggest_negative.surprise_percent,
                    "date": biggest_negative.earnings_date.isoformat()
                } if biggest_negative else None,
                "upcoming_earnings": [
                    {
                        "symbol": earning.symbol,
                        "date": earning.earnings_date.isoformat(),
                        "eps_forecast": earning.eps_forecast
                    }
                    for earning in sorted(earnings_data, key=lambda x: x.earnings_date)[:10]
                ],
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing earnings impact: {e}")
            return {}


class MarketIntelligence(LoggerMixin):
    """Main market intelligence coordinator."""
    
    def __init__(self, economic_api_key: str = None, twitter_api_key: str = None, 
                 reddit_api_key: str = None, earnings_api_key: str = None):
        self.economic_calendar = EconomicCalendar(economic_api_key)
        self.sentiment_analyzer = SocialSentimentAnalyzer(twitter_api_key, reddit_api_key)
        self.earnings_calendar = EarningsCalendar(earnings_api_key)
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    async def get_comprehensive_intelligence(self, symbols: List[str] = None,
                                           days_ahead: int = 7) -> Dict[str, Any]:
        """Get comprehensive market intelligence."""
        try:
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=days_ahead)
            
            # Get economic events
            economic_events = await self.economic_calendar.get_upcoming_events(days_ahead)
            economic_impact = self.economic_calendar.analyze_market_impact(economic_events)
            
            # Get earnings data
            earnings_data = await self.earnings_calendar.get_earnings_calendar(start_date, end_date, symbols)
            earnings_impact = self.earnings_calendar.analyze_earnings_impact(earnings_data)
            
            # Get sentiment data for symbols
            sentiment_data = {}
            if symbols:
                for symbol in symbols:
                    twitter_sentiment = await self.sentiment_analyzer.analyze_twitter_sentiment(symbol, 24)
                    reddit_sentiment = await self.sentiment_analyzer.analyze_reddit_sentiment(symbol, 24)
                    
                    all_sentiment = twitter_sentiment + reddit_sentiment
                    sentiment_trend = self.sentiment_analyzer.analyze_sentiment_trend(all_sentiment)
                    
                    sentiment_data[symbol] = {
                        "twitter_sentiment": self.sentiment_analyzer.analyze_sentiment_trend(twitter_sentiment),
                        "reddit_sentiment": self.sentiment_analyzer.analyze_sentiment_trend(reddit_sentiment),
                        "combined_sentiment": sentiment_trend,
                        "data_points": len(all_sentiment)
                    }
            
            # Generate market outlook
            market_outlook = self._generate_market_outlook(economic_impact, earnings_impact, sentiment_data)
            
            return {
                "economic_intelligence": {
                    "events": [event.to_dict() for event in economic_events],
                    "impact_analysis": economic_impact
                },
                "earnings_intelligence": {
                    "earnings": [earning.to_dict() for earning in earnings_data],
                    "impact_analysis": earnings_impact
                },
                "sentiment_intelligence": sentiment_data,
                "market_outlook": market_outlook,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive intelligence: {e}")
            return {}
    
    def _generate_market_outlook(self, economic_impact: Dict[str, Any],
                               earnings_impact: Dict[str, Any],
                               sentiment_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate overall market outlook."""
        try:
            outlook = {
                "overall_sentiment": "NEUTRAL",
                "risk_level": "MEDIUM",
                "key_factors": [],
                "recommendations": []
            }
            
            # Analyze economic impact
            economic_score = economic_impact.get("impact_score", 0)
            if economic_score > 10:
                outlook["key_factors"].append("High-impact economic events expected")
                outlook["risk_level"] = "HIGH"
            elif economic_score < 5:
                outlook["key_factors"].append("Low economic event impact expected")
                outlook["risk_level"] = "LOW"
            
            # Analyze earnings impact
            avg_surprise = earnings_impact.get("average_surprise", 0)
            if avg_surprise > 2:
                outlook["key_factors"].append("Positive earnings surprises")
                outlook["overall_sentiment"] = "BULLISH"
            elif avg_surprise < -2:
                outlook["key_factors"].append("Negative earnings surprises")
                outlook["overall_sentiment"] = "BEARISH"
            
            # Analyze sentiment data
            if sentiment_data:
                avg_sentiment = np.mean([data.get("current_sentiment", 0) for data in sentiment_data.values()])
                if avg_sentiment > 0.2:
                    outlook["key_factors"].append("Positive social sentiment")
                    if outlook["overall_sentiment"] == "NEUTRAL":
                        outlook["overall_sentiment"] = "BULLISH"
                elif avg_sentiment < -0.2:
                    outlook["key_factors"].append("Negative social sentiment")
                    if outlook["overall_sentiment"] == "NEUTRAL":
                        outlook["overall_sentiment"] = "BEARISH"
            
            # Generate recommendations
            if outlook["overall_sentiment"] == "BULLISH":
                outlook["recommendations"].extend([
                    "Consider increasing exposure to growth stocks",
                    "Monitor for potential overbought conditions",
                    "Focus on sectors benefiting from economic tailwinds"
                ])
            elif outlook["overall_sentiment"] == "BEARISH":
                outlook["recommendations"].extend([
                    "Consider defensive positioning",
                    "Monitor for potential oversold opportunities",
                    "Focus on quality and dividend-paying stocks"
                ])
            else:
                outlook["recommendations"].extend([
                    "Maintain balanced portfolio approach",
                    "Stay alert for changing market conditions",
                    "Consider dollar-cost averaging strategies"
                ])
            
            return outlook
            
        except Exception as e:
            self.logger.error(f"Error generating market outlook: {e}")
            return {"error": "Unable to generate outlook"}


# Global instances
economic_calendar = EconomicCalendar()
sentiment_analyzer = SocialSentimentAnalyzer()
earnings_calendar = EarningsCalendar()
market_intelligence = MarketIntelligence()


def get_economic_calendar() -> EconomicCalendar:
    """Get economic calendar instance."""
    return economic_calendar


def get_sentiment_analyzer() -> SocialSentimentAnalyzer:
    """Get sentiment analyzer instance."""
    return sentiment_analyzer


def get_earnings_calendar() -> EarningsCalendar:
    """Get earnings calendar instance."""
    return earnings_calendar


def get_market_intelligence() -> MarketIntelligence:
    """Get market intelligence instance."""
    return market_intelligence


# Utility functions
async def get_market_intelligence_report(symbols: List[str] = None, days_ahead: int = 7) -> Dict[str, Any]:
    """Get comprehensive market intelligence report."""
    return await market_intelligence.get_comprehensive_intelligence(symbols, days_ahead)


async def analyze_symbol_sentiment(symbol: str, hours_back: int = 24) -> Dict[str, Any]:
    """Analyze sentiment for a specific symbol."""
    try:
        twitter_sentiment = await sentiment_analyzer.analyze_twitter_sentiment(symbol, hours_back)
        reddit_sentiment = await sentiment_analyzer.analyze_reddit_sentiment(symbol, hours_back)
        
        all_sentiment = twitter_sentiment + reddit_sentiment
        combined_analysis = sentiment_analyzer.analyze_sentiment_trend(all_sentiment)
        
        return {
            "symbol": symbol,
            "twitter_analysis": sentiment_analyzer.analyze_sentiment_trend(twitter_sentiment),
            "reddit_analysis": sentiment_analyzer.analyze_sentiment_trend(reddit_sentiment),
            "combined_analysis": combined_analysis,
            "data_points": len(all_sentiment),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing symbol sentiment: {e}")
        return {}
