# Options-mini-Project
Collar Options Streamlit Platform

We built a Streamlit platform that calculates the option Greeks for the collar strategy by automatically pairing calls and puts. A protective collar is formed by buying the stock, longing a put, and shorting a call. Hence, the initial cost is the initial stock price + initial put’s long price - initial call’s short price, and the result is the option premium per share (100 shares is a contract).

Expiration PnL: number of shares * [max(put strike - stock price at expiration, 0) - max(stock price at expiration, 0) - (initial stock price + initial put long price - initial call short price)]

We initially tried with Yahoo Finance, but it rate-limited our requests, so we replaced it with MarketData.app. The dte and strikeLimit choose the listed expiration closest to the target number of days, and limit the chain to strikes near-the-money, which narrows the download size (so it might not contain strikes very out-of-the-money).

On the interactive page, the user can either select a put or a call. If the user chooses a long put, the platform automatically selects a short call, and vice versa. The selection works like a mirror. For example, the stock price is 100 and the selected put strike is 95, the mirrored call strike would be 105, and the call strike nearest 105 will be selected. For simplicity, the app estimates each option’s market value using Midpoint = (Bid + Ask) / 2, which is convenient but imperfect since the midpoint is not the exact price of the transaction and the fees are excluded. When Bid or Ask is missing, we use the last traded price.

Then, our Streamlit platform uses the Black-Scholes-Merton option-pricing model to calculate each option’s theoretical value. Since we have access to option’s strike, time to expiration, risk-free rate, dividend yield, the implied volatility, and the hypothetical stock price, we can calculate Delta, Gamma, Theta, and Vega. Then, we calculated the Greeks of the collar using position signs. For example, the collar’s delta is 1 + delta of the put - delta of call.

For a selected collar, we will demonstrate using an example. Let’s assume that we use AAPL ticker, 30 days to expiration, 100 shares, risk-free rate 0.04, and dividend yield 0.000, and with expiration date 2026-09-18. As we choose the long put anchor strike at 290, the sell call strike automatically sets to 320 by mirroring the current stock price of $305.65. The details are shown in the screenshot below.
<img width="2016" height="838" alt="2dbaebfa-c864-4567-8c7e-ac777eba4f07" src="https://github.com/user-attachments/assets/f01f0eb6-d4f9-4875-8268-17d2b658fc8c" />


Then, we produce two visualizations:
PnL across stock price and time
<img width="1905" height="915" alt="0027f277-513e-4814-b0e1-bd632f0d1de2" src="https://github.com/user-attachments/assets/91b51652-a795-44dc-bfc8-c93385e6b54a" />

Based on the current stock price, the platform computes 0.6 * current stock price and 1.4* current stock price as the lower and upper boundaries for this graph. Then, it divides the middle portion into 240 evenly spaced prices within the interval. For each of the prices, the platform computes the collar’s PnL under three time situations: today, halfway, and at expiration. The today and halfway curves use the Black-Scholes-Merton model to reprice the put and call at each assumed stock price. The at-expiration curve is computed using the payoff formula.

PnL across time and volatility
<img width="1958" height="1284" alt="1854053f-2d77-41ad-b6e4-9e2d5c5fb223" src="https://github.com/user-attachments/assets/7b1e2263-d30e-4187-9513-3cb37153e318" />

First, the user can set a stock price, ranging from 0.6*current stock price to 1.4*current stock price. The IV multiplier ranges from 0.5 to 1.5 and is evenly split into 35 values. Then, using the Black-Scholes-Merton formula, we can reprice the call and put for every combination of IV multiplier and days remaining.

Imperfections: 
This Streamlit project assumes constant interest rates, continuous dividends, and fixed implied volatility within each scenario. The midpoint prices may not be executable. Transaction costs, taxes, and early exercise are not considered in this project.
