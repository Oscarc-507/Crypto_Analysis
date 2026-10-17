import ccxt
import pandas as pd
import numpy as np
import requests


def enviar_tabla_telegram():
    # Verificar que la tabla_resumen exista
    if 'tabla_resumen' not in globals() or tabla_resumen.empty:
        print("No se encuentra la tabla_resumen. Por favor ejecuta las celdas anteriores primero.")
        return

    # Cabecera del mensaje
    # Usamos fuentes monospaciadas (formato bloque de código en Telegram) para que las columnas se alineen
    mensaje_lineas = []
    mensaje_lineas.append(f"📊 *REPORTE ALFA & BETA ({timeframe})*")
    mensaje_lineas.append("```")
    mensaje_lineas.append(f"{'TICKER':<6} | {'BETA':<5} | {'ALPHA':<7}")
    mensaje_lineas.append("-" * 24)

    # Agregar cada fila de la tabla redondeando los decimales para que quepa bien en móviles
    for ticker, row in tabla_resumen.iterrows():
        beta_val = f"{row['Beta']:.2f}"
        alpha_val = f"{row['Alpha']:.4f}"
        mensaje_lineas.append(f"{ticker:<6} | {beta_val:<5} | {alpha_val:<7}")

    mensaje_lineas.append("```")

    # Agregar un breve resumen interpretativo fuera del bloque de código para que sea legible
    mensaje_lineas.append("\n🔍 *Interpretación rápida:*")
    # Tomamos el top de mayor beta y el de mayor alpha para destacar en el mensaje
    top_beta = tabla_resumen['Beta'].idxmax()
    top_alpha = tabla_resumen['Alpha'].idxmax()

    mensaje_lineas.append(f"🚀 *Más agresivo (Beta alto):* {top_beta} ({tabla_resumen.loc[top_beta, 'Beta']:.2f})")
    mensaje_lineas.append(f"💪 *Mayor fuerza relativa (Alpha alto):* {top_alpha} ({tabla_resumen.loc[top_alpha, 'Alpha']:.4f})")

    # Unir todo el mensaje
    mensaje_final = "\n".join(mensaje_lineas)

    # Enviar usando la API de Telegram con soporte para MarkdownV2 o Markdown estándar
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje_final,
        "parse_mode": "Markdown"
    }

    try:
        respuesta = requests.post(url, json=payload)
        respuesta.raise_for_status()
        print("¡Tabla comparativa enviada con éxito a Telegram!")
        return respuesta.json()
    except Exception as e:
        print(f"Error al enviar la tabla a Telegram: {e}")
        return None


# Función principal para ejecutar el proceso
def main():
    # Usamos Kraken configurado
    exchange = ccxt.kraken({
        'enableRateLimit': True,
    })

    # Lista de tickers a analizar
    tickers = ["BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "LTC", "BCH", "AVAX"]
    symbols = [f"{ticker}/USDT" for ticker in tickers]

    timeframe = '1d'  # Velas diarias
    limit = 150

    df_precios = pd.DataFrame()

    for symbol in symbols:
        print(f"Descargando datos de {symbol}...")
        try:
            # Descargar las velas
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            # Crear DataFrame temporal
            df_temp = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
            df_temp.set_index('timestamp', inplace=True)

            # Extraer el nombre de la moneda (ej. 'BTC' de 'BTC/USDT')
            coin_name = symbol.split('/')[0]

            # Asignar la columna de precio de cierre al DataFrame principal
            df_precios[coin_name] = df_temp['close']
        except Exception as e:
            print(f"Error al descargar {symbol}: {e}")

    # Eliminar cualquier fila que tenga valores nulos por desajustes de tiempo
    df_precios.dropna(inplace=True)

    def calcular_alpha_beta_eficiente(df_precios, ventana):
        """
        df_precios: DataFrame donde el índice es la fecha/tiempo y las columnas son los tickers.
        Debe incluir una columna 'BTC'.
        """
        # 1. Calcular retornos logarítmicos (mucho más rápidos con NumPy)
        retornos = np.log(df_precios / df_precios.shift(1))

        # 2. Extraer retornos de BTC (Nuestra variable X)
        X = retornos['BTC']

        resultados_alpha = pd.DataFrame(index=retornos.index)
        resultados_beta = pd.DataFrame(index=retornos.index)

        # Precomputar métricas de BTC (X) para la Varianza O(1)
        sum_x = X.rolling(window=ventana).sum()
        sum_x2 = (X ** 2).rolling(window=ventana).sum()

        esperanza_x = sum_x / ventana
        esperanza_x2 = sum_x2 / ventana

        var_x = esperanza_x2 - (esperanza_x ** 2)

        # 3. Iterar sobre las altcoins y calcular mediante sumas móviles
        for altcoin in retornos.columns:
            if altcoin == 'BTC':
                continue

            Y = retornos[altcoin]

            # Calcular sumas móviles necesarias para Covarianza O(1)
            sum_y = Y.rolling(window=ventana).sum()
            sum_xy = (X * Y).rolling(window=ventana).sum()

            esperanza_y = sum_y / ventana
            esperanza_xy = sum_xy / ventana

            cov_xy = esperanza_xy - (esperanza_x * esperanza_y)

            # 4. Calcular Beta y Alpha
            beta = cov_xy / var_x

            # Alpha en la vela actual
            alpha = Y - (beta * X)

            # Guardar resultados
            resultados_beta[altcoin] = beta
            resultados_alpha[altcoin] = alpha

        return resultados_alpha, resultados_beta

    # Verificamos que tengamos la columna BTC y datos antes de calcular
    if 'BTC' in df_precios.columns and not df_precios.empty:
        alpha_df, beta_df = calcular_alpha_beta_eficiente(df_precios, 50)

        # 5. Obtener el último valor de Beta para cada ticker (la fila más reciente)
        ultimos_betas = beta_df.iloc[-1].dropna()

        # 6. Ordenar de mayor a menor Beta
        tickers_ordenados = ultimos_betas.sort_values(ascending=False)

        # 7. Filtrar los que tienen un Beta mayor a 1 (más volátiles que el mercado/BTC)
        umbral_beta = 1.0
        mejores_betas = tickers_ordenados[tickers_ordenados > umbral_beta]

        # print(f"\nTickers filtrados con Beta > {umbral_beta} (Ideales para tendencias alcistas fuertes):")
        # display(mejores_betas)
    else:
        # Evitar bloque else vacío que causa IndentationError en Python
        print("\nNo se pudieron descargar los datos suficientes, o falta BTC. Revisa los errores de arriba.")

    # Verificar que existan las variables de resultados
    if 'beta_df' in globals() and 'alpha_df' in globals():
        # Obtener el último valor (el más reciente) de Beta y Alpha para cada moneda
        ultimos_betas = beta_df.iloc[-1]
        ultimos_alphas = alpha_df.iloc[-1]

        # Crear el DataFrame resumido
        tabla_resumen = pd.DataFrame({
            'Beta': ultimos_betas,
            'Alpha': ultimos_alphas
        })

        # Definir una función para generar la interpretación de cada métrica
        def interpretar_metricas(row):
            beta = row['Beta']
            alpha = row['Alpha']

            # Interpretación de Beta
            if beta > 1.2:
                desc_beta = "Muy Volátil / Agresivo (Sigue a BTC con fuerza)"
            elif 0.8 <= beta <= 1.2:
                desc_beta = "Neutral (Movimiento similar a BTC)"
            elif 0 < beta < 0.8:
                desc_beta = "Defensivo (Menos sensible a movimientos de BTC)"
            else:
                desc_beta = "Inverso (Se mueve en dirección opuesta a BTC)"

            # Interpretación de Alpha
            if alpha > 0.001:
                desc_alpha = "Rendimiento Excedente Fuerte (Fuerza Relativa)"
            elif alpha < -0.001:
                desc_alpha = "Subrendimiento Fuerte (Debilidad Relativa)"
            else:
                desc_alpha = "Neutral / Estable"

            return f"Beta: {desc_beta} | Alpha: {desc_alpha}"

        # Aplicar la función para crear la columna de interpretación
        tabla_resumen['Interpretación'] = tabla_resumen.apply(interpretar_metricas, axis=1)

        # Ordenar por Beta descendente
        tabla_resumen = tabla_resumen.sort_values(by='Beta', ascending=False)

        # Mostrar la tabla formateada
        print("TABLA DE ALPHAS, BETAS E INTERPRETACIÓN (Última vela en " + timeframe + ").")
        # display(tabla_resumen)
    else:
        print(f"Por favor, ejecuta primero la celda anterior para generar 'alpha_df' y 'beta_df'. (timeframe={timeframe})")

    # Ejecutar el envío
    enviar_tabla_telegram()


if __name__ == "__main__":
    main()
