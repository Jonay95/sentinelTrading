-- ============================================
-- Sentinel Trading Minimal Database Schema
-- ============================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabla de Activos
CREATE TABLE assets (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    asset_type VARCHAR(20) NOT NULL,
    sector VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Datos de Mercado
CREATE TABLE market_data (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    close_price DECIMAL(15,6) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, timestamp)
);

-- Tabla de Predicciones
CREATE TABLE predictions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_price DECIMAL(15,6) NOT NULL,
    confidence_score DECIMAL(5,4),
    model_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Portafolios
CREATE TABLE portfolios (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id UUID DEFAULT uuid_generate_v4(), -- Simplificado sin RLS por ahora
    total_value DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Posiciones
CREATE TABLE positions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    quantity DECIMAL(15,6) NOT NULL,
    entry_price DECIMAL(15,6) NOT NULL,
    current_price DECIMAL(15,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices básicos
CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_market_data_asset_timestamp ON market_data(asset_id, timestamp DESC);
CREATE INDEX idx_predictions_asset_timestamp ON predictions(asset_id, timestamp DESC);
CREATE INDEX idx_positions_portfolio ON positions(portfolio_id);

-- Datos de ejemplo
INSERT INTO assets (symbol, name, asset_type, sector) VALUES
('AAPL', 'Apple Inc.', 'STOCK', 'Technology'),
('MSFT', 'Microsoft Corporation', 'STOCK', 'Technology'),
('GOOGL', 'Alphabet Inc.', 'STOCK', 'Technology'),
('BTC', 'Bitcoin', 'CRYPTO', 'Cryptocurrency'),
('ETH', 'Ethereum', 'CRYPTO', 'Cryptocurrency');

-- Permisos simples
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;
