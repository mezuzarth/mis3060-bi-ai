import yfinance as yf

aapl = yf.Ticker("AAPL")
income = aapl.quarterly_income_stmt  # rows = line items, columns = quarter-end dates

if income.empty:
    raise SystemExit("No data returned from Yahoo Finance. Check your connection or try again.")

latest = income.columns.max()  # most recent quarter-end date
revenue = income.loc["Total Revenue", latest]
net_income = income.loc["Net Income", latest]

print(f"Quarter ended: {latest.date()}")
print(f"Revenue:       ${revenue:,.0f}")
print(f"Net income:    ${net_income:,.0f}")