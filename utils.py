import yfinance as yf
import pandas as pd

def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="6mo")  # More history for moving averages!
        price_drop_7d = None
        price_drop_30d = None
        sma_20 = None
        sma_50 = None
        close_price = None
        rsi_14 = None

        if not hist.empty:
            close_price = hist['Close'][-1]
            if len(hist) >= 7:
                price_drop_7d = ((close_price - hist['Close'][-7]) / hist['Close'][-7]) * 100
            if len(hist) >= 21:
                price_drop_30d = ((close_price - hist['Close'][-21]) / hist['Close'][-21]) * 100
                sma_20 = hist['Close'][-20:].mean()
            if len(hist) >= 50:
                sma_50 = hist['Close'][-50:].mean()
            # RSI (14)
            delta = hist['Close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            avg_gain = up.rolling(14).mean()
            avg_loss = down.rolling(14).mean()
            rs = avg_gain / avg_loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi_14 = float(rsi_series[-1]) if not rsi_series.empty else None

        return {
            "name": info.get("longName", ticker),
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "price": info.get("regularMarketPrice", None),
            "pe": info.get("trailingPE", None),
            "pb": info.get("priceToBook", None),
            "eps": info.get("trailingEps", None),
            "roe": info.get("returnOnEquity", None),
            "price_drop_7d": price_drop_7d,
            "price_drop_30d": price_drop_30d,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "close_price": close_price,
            "rsi_14": rsi_14,
            "ticker": ticker
        }
    except Exception as e:
        return {"error": str(e)}

def score_stock(ticker, openai_key=None, batch=False):
    data = get_fundamentals(ticker)
    if data.get("error"):
        return data

    score = 0
    reasons = []
    explanation = []

    # Rule-based scoring and explanations (fundamental)
    if data["price_drop_30d"] is not None and data["price_drop_30d"] < -10:
        score += 20
        reasons.append("Significant 1-month price drop (>10%)")
        explanation.append(f"Price dropped {abs(data['price_drop_30d']):.2f}% in the last month (possible overreaction).")
    if data["pe"] is not None and data["pe"] < 18:
        score += 20
        reasons.append("Low P/E ratio (<18)")
        explanation.append(f"P/E ratio is {data['pe']:.2f}, which is low for its sector.")
    if data["roe"] is not None and data["roe"] > 0.12:
        score += 15
        reasons.append("High Return on Equity (>12%)")
        explanation.append(f"Return on Equity is strong at {data['roe'] * 100:.2f}%.")
    if data["eps"] is not None and data["eps"] > 0:
        score += 15
        reasons.append("EPS is positive")
        explanation.append(f"Earnings per share (EPS) is positive at {data['eps']:.2f}.")
    if data["pb"] is not None and data["pb"] < 3:
        score += 10
        reasons.append("Low Price/Book (<3)")
        explanation.append(f"Price/Book ratio is {data['pb']:.2f}, relatively attractive.")

    # Rule-based scoring and explanations (technical)
    if data["close_price"] and data["sma_20"]:
        if data["close_price"] > data["sma_20"]:
            explanation.append(f"Price is trading above its 20-day moving average ({data['sma_20']:.2f}) — momentum is positive.")
        else:
            explanation.append(f"Price is below its 20-day moving average ({data['sma_20']:.2f}) — could indicate short-term weakness.")
    if data["close_price"] and data["sma_50"]:
        if data["close_price"] > data["sma_50"]:
            explanation.append(f"Price is trading above its 50-day moving average ({data['sma_50']:.2f}) — longer-term uptrend.")
        else:
            explanation.append(f"Price is below its 50-day moving average ({data['sma_50']:.2f}) — longer-term trend may be weak.")
    if data["rsi_14"]:
        if data["rsi_14"] > 70:
            explanation.append(f"RSI(14) is {data['rsi_14']:.1f}: Overbought! Price may correct soon.")
        elif data["rsi_14"] < 30:
            explanation.append(f"RSI(14) is {data['rsi_14']:.1f}: Oversold! Could be a bounce opportunity.")
        else:
            explanation.append(f"RSI(14) is {data['rsi_14']:.1f}: In neutral range.")

    if score > 60:
        score += 10
        reasons.append("Multiple strong signals")
        explanation.append("Several strong value and momentum signals align (high-conviction pick).")
    if score < 40:
        explanation.append("No major valuation anomaly or sharp drop detected (mild opportunity).")

    summary = "; ".join(reasons)
    thesis = None

    # Add GPT-3.5 turbo thesis if API key present
    if openai_key and score > 0:
        try:
            thesis = generate_thesis(data, openai_key)
        except Exception as e:
            thesis = f"(AI thesis unavailable: {str(e)})"

    result = {
        "name": data.get("name", ticker),
        "ticker": ticker,
        "exchange": data.get("exchange", ""),
        "score": score,
        "summary": f"Signals: {summary}",
        "pe": data.get("pe"),
        "pb": data.get("pb"),
        "roe": data.get("roe"),
        "eps": data.get("eps"),
        "price_drop_7d": data.get("price_drop_7d"),
        "price_drop_30d": data.get("price_drop_30d"),
        "close_price": data.get("close_price"),
        "sma_20": data.get("sma_20"),
        "sma_50": data.get("sma_50"),
        "rsi_14": data.get("rsi_14"),
        "explanation": "\n".join([f"- {x}" for x in explanation]),
        "thesis": thesis
    }

    if thesis:
        result["explanation"] += f"\n\n**AI Thesis:** {thesis}"

    return result

def generate_thesis(data, openai_key):
    import openai
    client = openai.OpenAI(api_key=openai_key)
    prompt = (
        f"You're a seasoned investor texting a friend about this stock. "
        f"Here's what you know:\n"
        f"Stock: {data.get('name', data['ticker'])}\n"
        f"Exchange: {data.get('exchange', '')}\n"
        f"Sector: {data.get('sector', 'Unknown')}\n"
        f"Industry: {data.get('industry', 'Unknown')}\n"
        f"Score: {data.get('score')}/100\n"
        f"P/E: {data.get('pe')}, P/B: {data.get('pb')}, ROE: {data.get('roe')}, EPS: {data.get('eps')}, "
        f"1M Price Change: {data.get('price_drop_30d')}\n"
        f"Current Price: {data.get('close_price')}\n"
        f"SMA20: {data.get('sma_20')}, SMA50: {data.get('sma_50')}, RSI(14): {data.get('rsi_14')}\n\n"
        "In 2–3 sentences: First, tell me in plain English if you’d Buy, Watch, or Avoid, and why — don’t hedge, just give your gut. "
        "Second, compare it briefly to other stocks in its sector or industry (even if roughly). "
        "Third, mention one thing you’d keep an eye on (risk, valuation, news, whatever stands out). "
        "Be candid, conversational, and concrete — like you’re messaging a sharp investor friend, not writing a report."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()
