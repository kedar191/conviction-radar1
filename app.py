import streamlit as st
import yfinance as yf
from utils import score_stock
from tickers import batch_tickers

st.set_page_config(page_title="Conviction Radar", layout="wide")

st.title("📈 Conviction Radar – AI-Powered Undervalued Stock Scanner")
st.write("Scan US and Indian stocks for undervaluation, smart signals, and AI-generated thesis.")

openai_api_key = st.sidebar.text_input(
    "🔐 Enter your OpenAI API key (for AI explanations, optional)", type="password"
)

mode = st.sidebar.radio("Mode", ["Single Stock", "Batch Mode"], index=0)

if mode == "Single Stock":
    ticker = st.text_input("Enter a stock ticker (e.g., `AAPL`, `KOTAKBANK.NS`, `NVDA`):")
    if ticker:
        with st.spinner("Analyzing..."):
            result = score_stock(ticker, openai_api_key)
        if result.get("error"):
            st.error(result["error"])
        else:
            st.header(result["name"])
            st.write(f"**Exchange:** {result['exchange']}")
            st.metric("Conviction Score", f"{result['score']}/100")
            st.write(result["summary"])
            st.markdown(f"**Why flagged:**\n{result['explanation']}")
            st.write("----")
            st.json(result)
elif mode == "Batch Mode":
    st.write("Running batch scan on 100+ US and Indian stocks...")
    with st.spinner("Analyzing batch..."):
        results = []
        for t in batch_tickers:
            result = score_stock(t, openai_api_key, batch=True)
            if result.get("score", 0) > 0:
                results.append(result)
        top = sorted(results, key=lambda x: x["score"], reverse=True)[:20]
    st.subheader("Top Undervalued Picks:")
    for r in top:
        with st.expander(f"{r['name']} ({r['ticker']}) – Score: {r['score']}"):
            st.write(r["summary"])
            st.json({k: v for k, v in r.items() if k not in ["summary"]})

st.info("Built by Kedar & ChatGPT. Data via Yahoo Finance. Thesis by GPT-4 (optional).")
