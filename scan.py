import ccxt
import pandas as pd
import numpy as np
import requests

def enviar_tabla_telegram(tabla, tf):
    if tabla is None or tabla.empty:
        print("No hay datos para enviar.")
        return

    # Cabecera del mensaje
    mensaje_lineas = [
        f"📊 *REPORTE ALFA & BETA ({tf})*",
        "```",
        f"{'TICKER':<6} | {'BETA':<5} | {'ALPHA':<7}",
        "-" * 24
    ]

    # Filas
    for ticker, row in tabla.iterrows():
        mensaje_lineas.append(f"{ticker:<6} | {row['Beta']:<5.2f} | {row['Alpha']:<7.4f}")

    mensaje_lineas.append("```")

    # Resumen
    top_beta = tabla['Beta'].idxmax()
    top_alpha = tabla['Alpha'].idxmax()

    mensaje_lineas.extend([
        "\n🔍 *Interpretación rápida:*",
        f"🚀 *Más agresivo (Beta alto):* {top_beta} ({tabla.loc[top_beta, 'Beta']:.2f})",
        f"💪 *Mayor fuerza relativa (Alpha alto):* {top_alpha} ({tabla.loc[top_alpha, 'Alpha']:.4f})"
    ])

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "\n".join(mensaje_lineas),
        "parse_mode": "Markdown"
    }

    try:
        respuesta = requests.post(url, json=payload)
        respuesta.raise_for_status()
        print("¡Tabla comparativa enviada con éxito a Telegram!")
        return respuesta.json()
    except Exception as e:
        print(f"Error al enviar a Telegram: {e}")
        return None

# Descarga de datos
exchange = ccxt.kraken({'enableRateLimit': True})
tickers = ["BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "LTC", "BCH","AVAX", "CRV", "NEAR", "RUNE", "ETC", "ATOM"]
symbols = [f"{ticker}/USDT" for ticker in tickers]
timeframe = '1d'
limit = 150

df_precios = pd.DataFrame()

for symbol in symbols:
    print(f"Descargando {symbol}...")
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df_temp = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
        df_temp.set_index('timestamp', inplace=True)
        df_precios[symbol.split('/')[0]] = df_temp['close']
    except Exception as e:
        print(f"Error con {symbol}: {e}")

df_precios.dropna(inplace=True)

def calcular_alpha_beta_eficiente(df, ventana):
    retornos = np.log(df / df.shift(1))
    X = retornos['BTC']

    var_x = (X ** 2).rolling(window=ventana).mean() - (X.rolling(window=ventana).mean() ** 2)

    resultados_alpha, resultados_beta = pd.DataFrame(index=retornos.index), pd.DataFrame(index=retornos.index)

    for altcoin in retornos.columns.drop('BTC'):
        Y = retornos[altcoin]
        cov_xy = (X * Y).rolling(window=ventana).mean() - (X.rolling(window=ventana).mean() * Y.rolling(window=ventana).mean())

        beta = cov_xy / var_x
        alpha = Y - (beta * X)

        resultados_beta[altcoin] = beta
        resultados_alpha[altcoin] = alpha

    return resultados_alpha, resultados_beta

# Cálculo y resultados
tabla_resumen = pd.DataFrame()

if 'BTC' in df_precios.columns and not df_precios.empty:
    alpha_df, beta_df = calcular_alpha_beta_eficiente(df_precios, 50)

    ultimos_betas = beta_df.iloc[-1].dropna()
    mejores_betas = ultimos_betas[ultimos_betas > 1.0].sort_values(ascending=False)
    print(f"\nTickers con Beta > 1.0:")
    display(mejores_betas)

    tabla_resumen = pd.DataFrame({
        'Beta': ultimos_betas,
        'Alpha': alpha_df.iloc[-1]
    }).sort_values(by='Beta', ascending=False)

    def interpretar(row):
        b, a = row['Beta'], row['Alpha']
        desc_beta = "Muy Volátil" if b > 1.2 else "Neutral" if b >= 0.8 else "Defensivo" if b > 0 else "Inverso"
        desc_alpha = "Fuerza" if a > 0.001 else "Debilidad" if a < -0.001 else "Neutral"
        return f"Beta: {desc_beta} | Alpha: {desc_alpha}"

    tabla_resumen['Interpretación'] = tabla_resumen.apply(interpretar, axis=1)

    print(f"\nTABLA DE ALPHAS Y BETAS ({timeframe}):")
    display(tabla_resumen)
    enviar_tabla_telegram(tabla_resumen, timeframe)
else:
    print("\nDatos insuficientes para el análisis.")
