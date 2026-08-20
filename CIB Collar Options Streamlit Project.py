import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from datetime import date
from curl_cffi import requests

st.set_page_config(page_title="Option Collar Lab", page_icon="🛡️", layout="wide")


def bs(S, K, T, r, q, sigma, kind):
    T, sigma = max(T, 1e-8), max(sigma, 1e-8)
    d1 = (np.log(S/K) + (r-q+sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    sign = 1 if kind == "call" else -1
    price = sign*(S*np.exp(-q*T)*norm.cdf(sign*d1) - K*np.exp(-r*T)*norm.cdf(sign*d2))
    delta = sign*np.exp(-q*T)*norm.cdf(sign*d1)
    gamma = np.exp(-q*T)*norm.pdf(d1)/(S*sigma*np.sqrt(T))
    vega = S*np.exp(-q*T)*norm.pdf(d1)*np.sqrt(T)/100
    theta = (-S*np.exp(-q*T)*norm.pdf(d1)*sigma/(2*np.sqrt(T))
             - sign*r*K*np.exp(-r*T)*norm.cdf(sign*d2)
             + sign*q*S*np.exp(-q*T)*norm.cdf(sign*d1))/365
    return price, delta, gamma, theta, vega


def midpoint(row):
    bid, ask, last = row.get("bid", 0), row.get("ask", 0), row.get("lastPrice", 0)
    return (bid+ask)/2 if bid > 0 and ask > 0 else last


@st.cache_data(ttl=3600, show_spinner=False)
def market(ticker, target_days, token):
    url = f"https://api.marketdata.app/v1/options/chain/{ticker}/"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(url, params={"dte": target_days, "strikeLimit": 8}, headers=headers, timeout=30)
    if response.status_code not in (200, 203):
        raise ValueError(f"MarketData API returned {response.status_code}: {response.text[:160]}")
    data = response.json()
    if data.get("s") != "ok" or not data.get("strike"):
        raise ValueError(data.get("errmsg", "No option-chain data returned."))
    n = len(data["strike"])
    frame = pd.DataFrame({k: v for k, v in data.items() if isinstance(v, list) and len(v) == n})
    frame = frame.rename(columns={"iv": "impliedVolatility", "last": "lastPrice"})
    for col in ["strike", "bid", "ask", "lastPrice", "impliedVolatility", "underlyingPrice"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["strike", "impliedVolatility", "underlyingPrice"])
    expiry = pd.to_datetime(frame.expiration.iloc[0], unit="s").date().isoformat()
    return float(frame.underlyingPrice.iloc[0]), expiry, frame[frame.side.eq("call")].copy(), frame[frame.side.eq("put")].copy()


st.title("Protective Collar Analyzer")
st.caption("Long stock + long put + short call • option-chain data • Black–Scholes risk and P&L")

with st.sidebar:
    st.header("Position")
    ticker = st.text_input("Ticker", "AAPL").strip().upper()
    token = st.text_input("MarketData API token", type="password", help="AAPL works as a demo without a token. Other tickers require a free MarketData.app token.")
    target_days = st.number_input("Target days to expiration", 7, 365, 30, 7)
    shares = st.number_input("Shares", 100, 100000, 100, 100)
    r = st.number_input("Risk-free rate", 0.0, 0.30, 0.04, 0.005, format="%.3f")
    q = st.number_input("Dividend yield", 0.0, 0.20, 0.00, 0.005, format="%.3f")

try:
    with st.spinner("Loading option chain..."):
        spot, expiry, calls, puts = market(ticker, target_days, token)
except Exception as e:
    st.error(f"Could not load {ticker}: {e}")
    st.stop()

T = max((pd.Timestamp(expiry).date()-date.today()).days, 1)/365
st.sidebar.success(f"Using expiration {expiry}")
anchor = st.sidebar.radio("Choose the anchor leg", ["Long put", "Short call"], horizontal=True)
table = puts if anchor == "Long put" else calls
valid = table[(table.strike.between(spot*.70, spot*1.30)) & (table.impliedVolatility > 0)].copy()
if valid.empty:
    st.error("No usable strikes were returned. Try a different target expiration.")
    st.stop()

default_strike = spot*.95 if anchor == "Long put" else spot*1.05
strikes = valid.strike.round(2).tolist()
anchor_k = st.sidebar.selectbox("Anchor strike", strikes, index=int(np.argmin(np.abs(np.array(strikes)-default_strike))))
other = calls if anchor == "Long put" else puts
mirror = 2*spot-anchor_k
other_valid = other[(other.strike.between(spot*.70, spot*1.30)) & (other.impliedVolatility > 0)]
other_k = float(other_valid.iloc[(other_valid.strike-mirror).abs().argsort()[:1]].strike.iloc[0])
put_k, call_k = (anchor_k, other_k) if anchor == "Long put" else (other_k, anchor_k)
put = puts.iloc[(puts.strike-put_k).abs().argsort()[:1]].iloc[0]
call = calls.iloc[(calls.strike-call_k).abs().argsort()[:1]].iloc[0]
put_px, call_px = midpoint(put), midpoint(call)
put_iv, call_iv = float(put.impliedVolatility), float(call.impliedVolatility)
contracts = shares/100

st.sidebar.info(f"Buy {contracts:g} × {put_k:g} put; sell {contracts:g} × {call_k:g} call")
st.sidebar.caption("The second strike is the nearest available strike mirrored around the stock price.")

rows = []
for name, kind, K, premium, iv, weight in [("Long put", "put", put_k, put_px, put_iv, 1), ("Short call", "call", call_k, call_px, call_iv, -1)]:
    value, delta, gamma, theta, vega = bs(spot, K, T, r, q, iv, kind)
    rows.append([name, K, premium, iv, value, weight*delta, weight*gamma, weight*theta, weight*vega])

greeks = pd.DataFrame(rows, columns=["Leg", "Strike", "Market", "IV", "BS value", "Delta", "Gamma", "Theta/day", "Vega/1%"])
net_premium = put_px-call_px
net_delta = shares*(1+greeks.Delta.sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stock price", f"${spot:,.2f}")
c2.metric("Net option cost", f"${net_premium*shares:,.0f}")
c3.metric("Maximum loss", f"${max((spot+net_premium-put_k)*shares, 0):,.0f}")
c4.metric("Maximum profit", f"${max((call_k-spot-net_premium)*shares, 0):,.0f}")

st.subheader("Selected collar")
formats = {"Strike":"${:.2f}", "Market":"${:.2f}", "IV":"{:.1%}", "BS value":"${:.2f}", "Delta":"{:.3f}", "Gamma":"{:.4f}", "Theta/day":"{:.3f}", "Vega/1%":"{:.3f}"}
st.dataframe(greeks.style.format(formats), use_container_width=True, hide_index=True)
st.caption(f"Whole-position Greeks: Δ {net_delta:,.1f} | Γ {shares*greeks.Gamma.sum():,.3f} | Θ/day ${shares*greeks['Theta/day'].sum():,.2f} | Vega/1% ${shares*greeks['Vega/1%'].sum():,.2f}")

prices = np.linspace(spot*.6, spot*1.4, 240)
initial = spot+net_premium
expiry_pnl = (prices+np.maximum(put_k-prices, 0)-np.maximum(prices-call_k, 0)-initial)*shares
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(prices, expiry_pnl, lw=2, label="At expiration")
for days, label in [(max(int(T*365/2), 1), "Halfway"), (int(T*365), "Today")]:
    tau = days/365
    values = [x+bs(x, put_k, tau, r, q, put_iv, "put")[0]-bs(x, call_k, tau, r, q, call_iv, "call")[0] for x in prices]
    ax.plot(prices, (np.array(values)-initial)*shares, alpha=.75, label=label)
ax.axhline(0, color="black", lw=.8); ax.axvline(spot, color="gray", ls="--", lw=.8)
ax.set(xlabel="Stock price", ylabel="Total P&L ($)", title="P&L across stock price and time")
ax.legend(); ax.grid(alpha=.2); st.pyplot(fig)

st.subheader("P&L across time and volatility")
scenario = st.slider("Scenario stock price", float(prices.min()), float(prices.max()), float(spot), step=max(round(spot/200, 2), .01))
days, vols = np.linspace(1, max(int(T*365), 2), 35), np.linspace(.5, 1.5, 35)
surface = np.array([[(scenario+bs(scenario, put_k, d/365, r, q, put_iv*m, "put")[0]-bs(scenario, call_k, d/365, r, q, call_iv*m, "call")[0]-initial)*shares for d in days] for m in vols])
fig2, ax2 = plt.subplots(figsize=(9, 4))
img = ax2.imshow(surface, aspect="auto", origin="lower", extent=[days.min(), days.max(), vols.min(), vols.max()], cmap="RdYlGn")
ax2.set(xlabel="Days remaining", ylabel="IV multiplier", title=f"Mark-to-market P&L at ${scenario:.2f}")
fig2.colorbar(img, ax=ax2, label="P&L ($)"); st.pyplot(fig2)

st.caption("Educational model. MarketData.app free access may be delayed. Quotes and Black–Scholes assumptions exclude fees, taxes, early exercise, and assignment risk.")
