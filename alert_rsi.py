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
AGE_MAX = timedelta(minutes=35)


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
    # La dernière ligne est la bougie en cours : on prend les deux bougies closes d'avant
    actuel = valeurs.iloc[-2]
    precedent = valeurs.iloc[-3]
    cloture = close.index[-2].to_pydatetime() + DUREE_BOUGIE
    if cloture.tzinfo is None:
        cloture = cloture.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - cloture
    print(f"{nom}: RSI {precedent:.1f} -> {actuel:.1f} (bougie close il y a {age})")

    if age > AGE_MAX:
        print(f"{nom}: données trop anciennes, marché probablement fermé")
        return
    if precedent < SURACHETE <= actuel:
        telegram(f"🔴 {nom} SURACHETÉ : RSI {actuel:.1f} (>{SURACHETE}) en {INTERVALLE}")
    elif precedent > SURVENDU >= actuel:
        telegram(f"🟢 {nom} SURVENDU : RSI {actuel:.1f} (<{SURVENDU}) en {INTERVALLE}")


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
