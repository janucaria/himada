# Himada

**Himada — Historical Market Data Downloader**

Himada is a lightweight desktop GUI application for downloading historical market data using `yfinance` and exporting it as CSV files.

It provides a simple and practical way to obtain market data for analysis, research, or backtesting.

---

## Features

- Download by:
  - Date range (start / end)
  - Duration (1mo, 6mo, 1y, etc.)
  - Maximum available history
- Multiple tickers support
- Intraday intervals (subject to Yahoo Finance limitations)
- Optional auto-adjusted OHLC values
- Optional inclusion of dividends and splits
- Persistent settings (remembers previous inputs)
- CSV export

---

## Supported Ticker Formats

### US Stocks

```
AAPL
MSFT
TSLA
```

### Indonesian Stocks (IDX)

```
BBCA.JK
BBRI.JK
BMRI.JK
```

### Cryptocurrency

```
BTC-USD
ETH-USD
```

### Forex

```
EURUSD=X
```

Multiple tickers can be separated by commas or spaces:

```
AAPL, MSFT, TSLA
```

---

## Installation (Development)

From the project root directory:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -e .
```

Run the application:

```bash
python -m himada.app
```

---

## Building Executable (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed -n Himada src/himada/app.py
```

The executable will be generated in:

```
dist/Himada.exe
```

---

## Versioning

The application version is defined in:

```
pyproject.toml
```

Himada reads its version dynamically from package metadata.

Example display:

```
Himada v0.1.0
```

---

## Output Files

CSV naming format:

```
TICKER_INTERVAL_TAG.csv
```

Examples:

```
AAPL_1d_2023-01-01_2024-01-01.csv
BBCA.JK_1d_max.csv
BTC-USD_1h_60d.csv
```

These files can be used for analysis, research, or imported into other applications.

---

## Yahoo Finance Data Limitations

Yahoo Finance imposes limits on intraday historical data:

- `1m` interval → typically limited to ~7 days  
- Other intraday intervals → typically limited to ~60 days  

Himada automatically adjusts requests when necessary.

---

## License

This project is licensed under the **Apache License 2.0**, consistent with the `yfinance` project.

See the [`LICENSE`](LICENSE) file for details.
