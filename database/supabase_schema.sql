-- ============================================
-- Sentinel Trading Database Schema for Supabase
-- ============================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- 1. ASSETS TABLE
-- ============================================
CREATE TABLE assets (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    asset_type VARCHAR(20) NOT NULL CHECK (asset_type IN ('STOCK', 'CRYPTO', 'FOREX', 'COMMODITY')),
    exchange VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast symbol lookup
CREATE INDEX idx_assets_symbol ON assets(symbol);

-- ============================================
-- 2. MARKET DATA TABLE (Time Series)
-- ============================================
CREATE TABLE market_data (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price DECIMAL(15,6) NOT NULL,
    high_price DECIMAL(15,6) NOT NULL,
    low_price DECIMAL(15,6) NOT NULL,
    close_price DECIMAL(15,6) NOT NULL,
    volume BIGINT NOT NULL,
    adjusted_close DECIMAL(15,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint for unique asset-timestamp combination
    UNIQUE(asset_id, timestamp)
);

-- Indexes for time series queries
CREATE INDEX idx_market_data_asset_timestamp ON market_data(asset_id, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON market_data(timestamp DESC);

-- ============================================
-- 3. PREDICTIONS TABLE
-- ============================================
CREATE TABLE predictions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    prediction_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_price DECIMAL(15,6) NOT NULL,
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    model_version VARCHAR(50) NOT NULL,
    prediction_type VARCHAR(20) NOT NULL CHECK (prediction_type IN ('PRICE', 'DIRECTION', 'VOLATILITY')),
    time_horizon VARCHAR(20) NOT NULL CHECK (time_horizon IN ('1D', '1W', '1M', '3M')),
    actual_price DECIMAL(15,6),
    actual_timestamp TIMESTAMP WITH TIME ZONE,
    accuracy_score DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for prediction queries
CREATE INDEX idx_predictions_asset_timestamp ON predictions(asset_id, prediction_timestamp DESC);
CREATE INDEX idx_predictions_model_version ON predictions(model_version);
CREATE INDEX idx_predictions_accuracy ON predictions(accuracy_score DESC);

-- ============================================
-- 4. NEWS ARTICLES TABLE
-- ============================================
CREATE TABLE news_articles (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    source VARCHAR(100) NOT NULL,
    author VARCHAR(100),
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sentiment_score DECIMAL(5,4) CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_label VARCHAR(20) CHECK (sentiment_label IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')),
    confidence DECIMAL(5,4),
    keywords TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for news queries
CREATE INDEX idx_news_published_at ON news_articles(published_at DESC);
CREATE INDEX idx_news_sentiment ON news_articles(sentiment_score);
CREATE INDEX idx_news_source ON news_articles(source);

-- ============================================
-- 5. ASSET_NEWS_RELATION TABLE (Many-to-Many)
-- ============================================
CREATE TABLE asset_news_relation (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    news_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    relevance_score DECIMAL(5,4) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(asset_id, news_id)
);

-- Indexes
CREATE INDEX idx_asset_news_asset ON asset_news_relation(asset_id);
CREATE INDEX idx_asset_news_news ON asset_news_relation(news_id);
CREATE INDEX idx_asset_news_relevance ON asset_news_relation(relevance_score DESC);

-- ============================================
-- 6. ECONOMIC EVENTS TABLE
-- ============================================
CREATE TABLE economic_events (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    country VARCHAR(10) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_value DECIMAL(15,6),
    forecast_value DECIMAL(15,6),
    previous_value DECIMAL(15,6),
    impact_level VARCHAR(20) CHECK (impact_level IN ('LOW', 'MEDIUM', 'HIGH', 'EXTREME')),
    importance INTEGER CHECK (importance >= 1 AND importance <= 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for economic events
CREATE INDEX idx_economic_events_date ON economic_events(event_date DESC);
CREATE INDEX idx_economic_events_country ON economic_events(country);
CREATE INDEX idx_economic_events_impact ON economic_events(impact_level);

-- ============================================
-- 7. PORTFOLIOS TABLE
-- ============================================
CREATE TABLE portfolios (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    user_id VARCHAR(100) NOT NULL,
    total_value DECIMAL(15,2) DEFAULT 0,
    cash_balance DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);

-- ============================================
-- 8. POSITIONS TABLE
-- ============================================
CREATE TABLE positions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    quantity DECIMAL(15,6) NOT NULL,
    entry_price DECIMAL(15,6) NOT NULL,
    current_price DECIMAL(15,6),
    entry_date TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_date TIMESTAMP WITH TIME ZONE,
    position_type VARCHAR(20) NOT NULL CHECK (position_type IN ('LONG', 'SHORT')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'PARTIAL')),
    stop_loss_price DECIMAL(15,6),
    take_profit_price DECIMAL(15,6),
    unrealized_pnl DECIMAL(15,2),
    realized_pnl DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_positions_portfolio ON positions(portfolio_id);
CREATE INDEX idx_positions_asset ON positions(asset_id);
CREATE INDEX idx_positions_status ON positions(status);

-- ============================================
-- 9. TRANSACTIONS TABLE
-- ============================================
CREATE TABLE transactions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('BUY', 'SELL', 'DIVIDEND')),
    quantity DECIMAL(15,6) NOT NULL,
    price DECIMAL(15,6) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    commission DECIMAL(15,2) DEFAULT 0,
    fees DECIMAL(15,2) DEFAULT 0,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    external_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_transactions_position ON transactions(position_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp DESC);
CREATE INDEX idx_transactions_type ON transactions(transaction_type);

-- ============================================
-- 10. ALERTS TABLE
-- ============================================
CREATE TABLE alerts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    alert_condition JSONB NOT NULL,
    threshold_value DECIMAL(15,6) NOT NULL,
    comparison_operator VARCHAR(20) NOT NULL CHECK (comparison_operator IN ('>', '<', '>=', '<=', '=', '!=', 'CROSS_ABOVE', 'CROSS_BELOW')),
    is_active BOOLEAN DEFAULT true,
    triggered_count INTEGER DEFAULT 0,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_alerts_user ON alerts(user_id);
CREATE INDEX idx_alerts_active ON alerts(is_active);
CREATE INDEX idx_alerts_asset ON alerts(asset_id);

-- ============================================
-- 11. ALERT_HISTORY TABLE
-- ============================================
CREATE TABLE alert_history (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    trigger_value DECIMAL(15,6) NOT NULL,
    message TEXT NOT NULL,
    notification_sent BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_alert_history_alert ON alert_history(alert_id);
CREATE INDEX idx_alert_history_triggered ON alert_history(triggered_at DESC);

-- ============================================
-- 12. RISK_METRICS TABLE
-- ============================================
CREATE TABLE risk_metrics (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    calculation_date TIMESTAMP WITH TIME ZONE NOT NULL,
    var_95 DECIMAL(15,2),
    var_99 DECIMAL(15,2),
    expected_shortfall DECIMAL(15,2),
    max_drawdown DECIMAL(15,4),
    current_drawdown DECIMAL(15,4),
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    beta DECIMAL(10,4),
    volatility DECIMAL(10,4),
    diversification_score DECIMAL(5,4),
    concentration_risk DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_risk_metrics_portfolio ON risk_metrics(portfolio_id);
CREATE INDEX idx_risk_metrics_date ON risk_metrics(calculation_date DESC);

-- ============================================
-- 13. SYSTEM_LOGS TABLE
-- ============================================
CREATE TABLE system_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL CHECK (log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    module VARCHAR(100),
    user_id VARCHAR(100),
    asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_system_logs_level ON system_logs(log_level);
CREATE INDEX idx_system_logs_created ON system_logs(created_at DESC);
CREATE INDEX idx_system_logs_user ON system_logs(user_id);

-- ============================================
-- 14. MODEL_VERSIONS TABLE
-- ============================================
CREATE TABLE model_versions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    accuracy_score DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall_score DECIMAL(5,4),
    f1_score DECIMAL(5,4),
    training_data_start TIMESTAMP WITH TIME ZONE,
    training_data_end TIMESTAMP WITH TIME ZONE,
    model_parameters JSONB,
    model_file_path TEXT,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(model_name, version)
);

-- Indexes
CREATE INDEX idx_model_versions_name ON model_versions(model_name);
CREATE INDEX idx_model_versions_active ON model_versions(is_active);
CREATE INDEX idx_model_versions_accuracy ON model_versions(accuracy_score DESC);

-- ============================================
-- TRIGGERS FOR UPDATED_AT COLUMNS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for tables with updated_at
CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON assets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_portfolios_updated_at BEFORE UPDATE ON portfolios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- Current portfolio positions view
CREATE VIEW current_positions AS
SELECT 
    p.id,
    p.portfolio_id,
    p.asset_id,
    a.symbol,
    a.name as asset_name,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.unrealized_pnl,
    p.position_type,
    p.status,
    p.entry_date,
    (p.quantity * p.current_price) as market_value
FROM positions p
JOIN assets a ON p.asset_id = a.id
WHERE p.status = 'OPEN';

-- Recent predictions view
CREATE VIEW recent_predictions AS
SELECT 
    pred.id,
    pred.asset_id,
    a.symbol,
    pred.predicted_price,
    pred.confidence_score,
    pred.model_version,
    pred.prediction_type,
    pred.time_horizon,
    pred.prediction_timestamp,
    pred.actual_price,
    pred.accuracy_score,
    CASE 
        WHEN pred.actual_price IS NOT NULL THEN 
            ABS(pred.predicted_price - pred.actual_price) / pred.actual_price * 100
        ELSE NULL 
    END as error_percentage
FROM predictions pred
JOIN assets a ON pred.asset_id = a.id
ORDER BY pred.prediction_timestamp DESC;

-- Portfolio performance view
CREATE VIEW portfolio_performance AS
SELECT 
    portfolio_id,
    SUM(CASE WHEN position_type = 'LONG' THEN unrealized_pnl ELSE 0 END) as long_pnl,
    SUM(CASE WHEN position_type = 'SHORT' THEN unrealized_pnl ELSE 0 END) as short_pnl,
    SUM(unrealized_pnl) as total_pnl,
    SUM(quantity * current_price) as total_market_value,
    COUNT(*) as position_count
FROM current_positions
GROUP BY portfolio_id;

-- ============================================
-- SAMPLE DATA INSERTION
-- ============================================

-- Insert some sample assets
INSERT INTO assets (symbol, name, asset_type, sector, exchange) VALUES
('AAPL', 'Apple Inc.', 'STOCK', 'Technology', 'NASDAQ'),
('MSFT', 'Microsoft Corporation', 'STOCK', 'Technology', 'NASDAQ'),
('GOOGL', 'Alphabet Inc.', 'STOCK', 'Technology', 'NASDAQ'),
('AMZN', 'Amazon.com Inc.', 'STOCK', 'Consumer Discretionary', 'NASDAQ'),
('TSLA', 'Tesla Inc.', 'STOCK', 'Automotive', 'NASDAQ'),
('BTC', 'Bitcoin', 'CRYPTO', 'Cryptocurrency', 'Binance'),
('ETH', 'Ethereum', 'CRYPTO', 'Cryptocurrency', 'Binance');

-- Insert sample portfolio
INSERT INTO portfolios (name, description, user_id, total_value, cash_balance) VALUES
('Main Portfolio', 'My main trading portfolio', 'demo_user', 100000.00, 10000.00);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on user-specific tables
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own portfolios" ON portfolios
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own portfolios" ON portfolios
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own portfolios" ON portfolios
    FOR UPDATE USING (user_id = auth.uid());

-- Similar policies for positions (through portfolio relationship)
CREATE POLICY "Users can view positions in their portfolios" ON positions
    FOR SELECT USING (
        portfolio_id IN (
            SELECT id FROM portfolios WHERE user_id = auth.uid()
        )
    );

-- Similar policies for alerts
CREATE POLICY "Users can view their own alerts" ON alerts
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own alerts" ON alerts
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own alerts" ON alerts
    FOR UPDATE USING (user_id = auth.uid());

-- ============================================
-- GRANTS
-- ============================================

-- Grant necessary permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;
