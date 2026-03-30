-- ============================================
-- Sentinel Trading Database Schema for Supabase (Fixed Version)
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
-- 4. PORTFOLIOS TABLE
-- ============================================
CREATE TABLE portfolios (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, -- Changed to UUID reference
    total_value DECIMAL(15,2) DEFAULT 0,
    cash_balance DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);

-- ============================================
-- 5. POSITIONS TABLE
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
-- 6. ALERTS TABLE
-- ============================================
CREATE TABLE alerts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, -- Changed to UUID reference
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

-- ============================================
-- ROW LEVEL SECURITY (RLS) - FIXED VERSION
-- ============================================

-- Enable RLS on user-specific tables
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- RLS Policies (Fixed UUID comparison)
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

-- Grant permissions on individual views (after they are created)
GRANT SELECT ON current_positions TO anon;
GRANT SELECT ON current_positions TO authenticated;
GRANT SELECT ON recent_predictions TO anon;
GRANT SELECT ON recent_predictions TO authenticated;
GRANT SELECT ON portfolio_performance TO anon;
GRANT SELECT ON portfolio_performance TO authenticated;
