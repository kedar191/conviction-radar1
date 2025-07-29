import yfinance as yf

def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1mo")
        price_drop_7d = None
        price_drop_30d = None
        if len(hist) >= 7:
            price_drop_7d = ((hist['Close'][-1] - hist['Close'][-7]) / hist['Close'][-7]) * 100
        if len(hist) >= 21:
            price_drop_30d = ((hist['Close'][-1] - hist['Close'][0]) / hist['Close'][0]) * 100
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

    # Rule-based scoring and explanations
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
    if score > 60:
        score += 10
        reasons.append("Multiple strong signals")
        explanation.append("Several strong value signals align (high-conviction pick).")
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
        "explanation": "\n".join([f"- {x}" for x in explanation]),
        "thesis": thesis
    }

    if thesis:
        result["explanation"] += f"\n\n**AI Thesis:** {thesis}"

    return result

def generate_thesis(data, openai_key):
    import openai
    # This uses ONLY GPT-3.5-turbo
    prompt = (
        f"Stock: {data.get('name', data['ticker'])}\n"
        f"Exchange: {data.get('exchange', '')}\n"
        f"P/E: {data.get('pe')}, P/B: {data.get('pb')}, ROE: {data.get('roe')}, "
        f"EPS: {data.get('eps')}, 1M Price Drop: {data.get('price_drop_30d')}\n"
        "Write a one-sentence summary for a savvy investor: "
        "Is this a potentially undervalued opportunity? Use only data above."
    )
    client = openai.OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # This line enforces 3.5-turbo only
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()
