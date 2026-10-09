import ccxt
import pandas as pd

# Instanciamos Kraken (no requiere apiKey ni secret para datos de mercado)
exchange = ccxt.kraken({
    'enableRateLimit': True,  # Respeta automáticamente los límites de peticiones
})

symbol = 'BTC/USDT'  # o 'BTC/USD'
timeframe = '1h'      # '1m', '5m', '15m', '1h', '1d'
limit = 100           # Cantidad de velas a consultar

# fetch_ohlcv devuelve: [timestamp, open, high, low, close, volume]
candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

# Estructurar los datos en un DataFrame de pandas
df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

print(df.tail())
