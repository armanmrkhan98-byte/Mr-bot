import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class MarketSignalEngine:
    def __init__(self, df: pd.DataFrame):
        # Yahan hum ensure karte hain ki live/running candle ko ignore kar diya jaye,
        # taaki TA-Lib sirf poori tarah close ho chuki candles par chale.
        self.df = df.iloc[:-1].copy() if len(df) > 30 else df

    def analyze_indicators(self) -> Dict[str, Any]:
        close = self.df['close'].values
        rsi = talib.RSI(close, timeperiod=14)
        ema_fast = talib.EMA(close, timeperiod=9)
        ema_slow = talib.EMA(close, timeperiod=21)
        
        return {
            "rsi": rsi[-1],
            "ema_fast": ema_fast[-1],
            "ema_slow": ema_slow[-1],
            "trend": "BULLISH" if ema_fast[-1] > ema_slow[-1] else "BEARISH"
        }

    def detect_candle_patterns(self) -> Dict[str, str]:
        open_p = self.df['open'].values
        high_p = self.df['high'].values
        low_p = self.df['low'].values
        close_p = self.df['close'].values

        engulfing = talib.CDLENGULFING(open_p, high_p, low_p, close_p)
        hammer = talib.CDLHAMMER(open_p, high_p, low_p, close_p)
        shooting_star = talib.CDLSHOOTINGSTAR(open_p, high_p, low_p, close_p)
        doji = talib.CDLDOJI(open_p, high_p, low_p, close_p)

        latest_engulfing = engulfing[-1]
        latest_hammer = hammer[-1]
        latest_star = shooting_star[-1]
        latest_doji = doji[-1]

        signal = "NEUTRAL"
        pattern_name = "NONE"

        if latest_engulfing == 100 or latest_hammer == 100:
            signal = "CALL"
            pattern_name = "Bullish Engulfing/Hammer"
        elif latest_engulfing == -100 or latest_star == -100:
            signal = "PUT"
            pattern_name = "Bearish Engulfing/Shooting Star"
        elif latest_doji != 0:
            pattern_name = "Doji"

        return {"pattern": pattern_name, "pattern_signal": signal}

    def generate_trading_signal(self) -> Dict[str, Any]:
        indicators = self.analyze_indicators()
        patterns = self.detect_candle_patterns()

        rsi = indicators["rsi"]
        trend = indicators["trend"]
        pattern_sig = patterns["pattern_signal"]

        decision = "HOLD"
        confidence = 0.0

        if trend == "BULLISH" and pattern_sig == "CALL" and rsi < 70:
            decision = "CALL"
            confidence = 0.85
        elif trend == "BEARISH" and pattern_sig == "PUT" and rsi > 30:
            decision = "PUT"
            confidence = 0.85
        elif pattern_sig == "CALL" and rsi < 30:
            decision = "CALL"
            confidence = 0.75
        elif pattern_sig == "PUT" and rsi > 70:
            decision = "PUT"
            confidence = 0.75

        return {
            "action": decision,
            "confidence": confidence,
            "pattern": patterns["pattern"],
            "rsi": round(rsi, 2),
            "trend": trend
        }

app = FastAPI(title="Pocket Option AI Signal API")

class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float

class CandleData(BaseModel):
    symbol: str
    is_otc: bool
    candles: List[Candle]

@app.post("/analyze")
async def analyze_market(data: CandleData):
    if len(data.candles) < 31:
        raise HTTPException(status_code=400, detail="Minimum 31 candles required.")

    df = pd.DataFrame([c.dict() for c in data.candles])
    engine = MarketSignalEngine(df)
    result = engine.generate_trading_signal()
    result["symbol"] = data.symbol
    result["is_otc"] = data.is_otc

    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
          
