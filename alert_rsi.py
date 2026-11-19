import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import yfinance as yf

# Actifs surveillés : nom affiché -> symbole Yahoo Finance
ACTIFS = {
    "OR (XAUUSD)": "GC=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "NASDAQ": "^IXIC",
    "S&P 500": "^GSPC",
    "DAX": "^GDAXI",
    "CAC 40": "^FCHI",
    "PETROLE": "CL=F",
    "APPLE": "AAPL",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
}
PERIODE_RSI = 14
SURACHETE = 70
SURVENDU = 30
INTERVALLE = "15m"
DUREE_BOUGIE = timedelta(minutes=15)
# Ignore les signaux trop vieux (marché fermé, week-end)
AGE_MAX = timedelta(minutes=80)
LOOKBACK = 5  # nombre de bougies closes examinées


def rsi(close: pd.Series, n: int = PERIODE_RSI) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    perte = -delta.clip(upper=0)
    moy_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    moy_perte = perte.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = moy_gain / moy_perte
    return 100 - 100 / (1 + rs)


def telegram(message: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=20,
    )
    r.raise_for_status()


def verifier(nom: str, symbole: str) -> None:
    df = yf.download(
        symbole, period="5d", interval=INTERVALLE, progress=False, auto_adjust=True
    )
    if df.empty:
        print(f"{nom}: pas de données")
        return
    close = df["Close"].squeeze().dropna()
    valeurs = rsi(close)
    maintenant = datetime.now(timezone.utc)
    print(f"{nom}: RSI {valeurs.iloc[-3]:.1f} -> {valeurs.iloc[-2]:.1f}")

    # On examine les dernières bougies closes (la toute dernière est en cours)
    for i in range(-LOOKBACK - 1, -1):
        actuel = valeurs.iloc[i]
        precedent = valeurs.iloc[i - 1]
        cloture = close.index[i].to_pydatetime() + DUREE_BOUGIE
        if cloture.tzinfo is None:
            cloture = cloture.replace(tzinfo=timezone.utc)
        age = maintenant - cloture
        if age > AGE_MAX:
            continue
        minutes = int(age.total_seconds() // 60)
        if precedent < SURACHETE <= actuel:
            telegram(
                f"🔴 {nom} SURACHETÉ : RSI {actuel:.1f} (>{SURACHETE}) "
                f"en {INTERVALLE}, il y a {minutes} min"
            )
        elif precedent > SURVENDU >= actuel:
            telegram(
                f"🟢 {nom} SURVENDU : RSI {actuel:.1f} (<{SURVENDU}) "
                f"en {INTERVALLE}, il y a {minutes} min"
            )


def main() -> None:
    if os.environ.get("TEST") == "true":
        telegram("✅ Test OK : ton alerte RSI fonctionne.")
    for nom, symbole in ACTIFS.items():
        try:
            verifier(nom, symbole)
        except Exception as e:  # une erreur sur un actif ne bloque pas l'autre
            print(f"{nom}: erreur {e}")


if __name__ == "__main__":
    main()
