INSERT INTO venue_instrument_specs
    (exchange, symbol, ct_val, lot_size, tick_size, min_size, source)
VALUES
    ('okx',     'BTC-USDT-SWAP', 0.01, 0.01,  0.1,  0.01,  'db'),
    ('okx',     'ETH-USDT-SWAP', 0.1,  0.01,  0.01, 0.01,  'db'),
    ('binance', 'BTC-USDT-SWAP', 1.0,  0.001, 0.1,  0.001, 'db'),
    ('binance', 'ETH-USDT-SWAP', 1.0,  0.001, 0.01, 0.001, 'db')
ON CONFLICT (exchange, symbol) DO UPDATE SET
    ct_val = EXCLUDED.ct_val,
    lot_size = EXCLUDED.lot_size,
    tick_size = EXCLUDED.tick_size,
    min_size = EXCLUDED.min_size,
    source = EXCLUDED.source,
    updated_at = NOW();
