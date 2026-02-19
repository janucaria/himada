import sys
from dataclasses import dataclass
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version as pkg_version

import pandas as pd
import yfinance as yf

from PySide6.QtCore import QDate, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from himada import APP_NAME, APP_VERSION


@dataclass
class DownloadConfig:
    tickers: list[str]
    interval: str
    include_actions: bool
    auto_adjust: bool
    out_dir: Path
    mode: str  # "range" | "period" | "max"
    start: str | None = None
    end: str | None = None
    period: str | None = None


def enforce_yahoo_limits(interval: str, requested_mode: str, requested_period: str | None, log):
    """
    Practical Yahoo/yfinance limitations:
    - Intraday (<1d) generally cannot extend past ~60d
    - 1m is often limited to ~7d
    We clamp only for mode=period/max to reduce confusion.
    """
    intraday = interval in {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
    if not intraday:
        return requested_mode, requested_period

    longish = {None, "max", "ytd", "10y", "5y", "2y", "1y", "6mo", "3mo"}
    if requested_mode in {"max", "period"} and requested_period in longish:
        if interval == "1m":
            log("⚠️ Interval=1m is limited by Yahoo; clamping period to 7d.")
            return "period", "7d"
        log("⚠️ Intraday intervals are limited by Yahoo; clamping period to 60d.")
        return "period", "60d"

    return requested_mode, requested_period


def fetch_and_save_csv(cfg: DownloadConfig, log) -> None:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    # Clamp if needed (mainly affects period/max with intraday)
    cfg.mode, cfg.period = enforce_yahoo_limits(cfg.interval, cfg.mode, cfg.period, log)

    for t in cfg.tickers:
        ticker = t.strip()
        if not ticker:
            continue

        log(f"Fetching: {ticker} | interval={cfg.interval} | mode={cfg.mode}")

        try:
            tk = yf.Ticker(ticker)

            if cfg.mode == "range":
                df = tk.history(
                    start=cfg.start,
                    end=cfg.end,
                    interval=cfg.interval,
                    actions=cfg.include_actions,
                    auto_adjust=cfg.auto_adjust,
                )
                file_tag = f"{cfg.start}_{cfg.end}"

            elif cfg.mode == "period":
                period = cfg.period or "1mo"
                df = tk.history(
                    period=period,
                    interval=cfg.interval,
                    actions=cfg.include_actions,
                    auto_adjust=cfg.auto_adjust,
                )
                file_tag = period

            else:  # cfg.mode == "max"
                df = tk.history(
                    period="max",
                    interval=cfg.interval,
                    actions=cfg.include_actions,
                    auto_adjust=cfg.auto_adjust,
                )
                file_tag = "max"

        except Exception as e:
            log(f"❌ Error fetching {ticker}: {e}")
            continue

        if df is None or df.empty:
            log(f"⚠️ No data returned for {ticker}.")
            continue

        # Make it CSV-friendly
        df = df.copy()
        df.index.name = "Date"
        df.reset_index(inplace=True)

        # Remove timezone info if present
        if "Date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Date"]):
            try:
                df["Date"] = df["Date"].dt.tz_localize(None)
            except Exception:
                pass

        out_file = cfg.out_dir / f"{ticker.replace('/', '_')}_{cfg.interval}_{file_tag}.csv"
        try:
            df.to_csv(out_file, index=False)
            log(f"✅ Saved: {out_file}")
        except Exception as e:
            log(f"❌ Error saving {ticker}: {e}")


class HimadaApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Historical Market Data Downloader")
        self.resize(820, 560)

        layout = QVBoxLayout(self)

        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        layout.addWidget(title)

        subtitle = QLabel(f"Historical Market Data Downloader (yfinance) — v{APP_VERSION}")
        layout.addWidget(subtitle)

        # Tickers row
        row_t = QHBoxLayout()
        row_t.addWidget(QLabel("Tickers (comma/space/newline separated):"))
        self.tickers = QLineEdit("BBCA.JK")
        row_t.addWidget(self.tickers)
        layout.addLayout(row_t)

        # Mode row
        row_m = QHBoxLayout()
        row_m.addWidget(QLabel("Download mode:"))

        self.mode = QComboBox()
        self.mode.addItems(["Date range (start/end)", "Duration (period)", "Maximum available (max)"])
        self.mode.setCurrentText("Maximum available (max)")
        row_m.addWidget(self.mode)

        row_m.addWidget(QLabel("Duration/Period:"))
        self.period = QComboBox()
        self.period.addItems(["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"])
        self.period.setCurrentText("max")
        row_m.addWidget(self.period)

        row_m.addStretch(1)
        layout.addLayout(row_m)

        # Dates row
        row_d = QHBoxLayout()
        row_d.addWidget(QLabel("Start:"))
        self.start = QDateEdit()
        self.start.setCalendarPopup(True)
        self.start.setDate(QDate.currentDate().addYears(-1))
        row_d.addWidget(self.start)

        row_d.addWidget(QLabel("End:"))
        self.end = QDateEdit()
        self.end.setCalendarPopup(True)
        self.end.setDate(QDate.currentDate())
        row_d.addWidget(self.end)

        row_d.addStretch(1)
        layout.addLayout(row_d)

        # Interval + options row
        row_i = QHBoxLayout()
        row_i.addWidget(QLabel("Interval:"))
        self.interval = QComboBox()
        self.interval.addItems(["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "2m", "1m"])
        self.interval.setCurrentText("1d")
        row_i.addWidget(self.interval)

        self.actions = QCheckBox("Include actions (dividends/splits)")
        self.actions.setChecked(False)
        row_i.addWidget(self.actions)

        self.auto_adjust = QCheckBox("Auto-adjust (OHLC adjusted)")
        self.auto_adjust.setChecked(True)
        row_i.addWidget(self.auto_adjust)

        row_i.addStretch(1)
        layout.addLayout(row_i)

        # Output folder row
        row_o = QHBoxLayout()
        row_o.addWidget(QLabel("Output folder:"))
        self.out_dir = QLineEdit(str(Path.home() / "himada_csv"))
        row_o.addWidget(self.out_dir)

        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self.browse_folder)
        row_o.addWidget(btn_browse)
        layout.addLayout(row_o)

        # Buttons row
        row_btn = QHBoxLayout()
        self.btn_download = QPushButton("Download → CSV")
        self.btn_download.clicked.connect(self.download)
        row_btn.addWidget(self.btn_download)

        self.btn_clear = QPushButton("Clear Log")
        self.btn_clear.clicked.connect(lambda: self.log.setPlainText(""))
        row_btn.addWidget(self.btn_clear)

        row_btn.addStretch(1)
        layout.addLayout(row_btn)

        # Log area
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # UX: enable/disable inputs based on mode
        self.mode.currentIndexChanged.connect(self.update_mode_ui)
        self.update_mode_ui()

        self.settings = QSettings("Janucaria", "Himada")  # organization, app
        self.load_settings()
        self.bind_persistence()
        
    def bind_persistence(self):
        # Save on change (nice UX)
        self.tickers.textChanged.connect(self.save_settings)
        self.mode.currentIndexChanged.connect(self.save_settings)
        self.period.currentIndexChanged.connect(self.save_settings)
        self.start.dateChanged.connect(self.save_settings)
        self.end.dateChanged.connect(self.save_settings)
        self.interval.currentIndexChanged.connect(self.save_settings)
        self.actions.stateChanged.connect(self.save_settings)
        self.auto_adjust.stateChanged.connect(self.save_settings)
        self.out_dir.textChanged.connect(self.save_settings)

    def load_settings(self):
        s = self.settings

        # Window geometry
        geom = s.value("window/geometry")
        if geom is not None:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass

        # Text fields
        self.tickers.setText(s.value("ui/tickers", self.tickers.text()))
        self.out_dir.setText(s.value("ui/out_dir", self.out_dir.text()))

        # Combos
        self.mode.setCurrentIndex(int(s.value("ui/mode_index", self.mode.currentIndex())))
        self.period.setCurrentIndex(int(s.value("ui/period_index", self.period.currentIndex())))
        self.interval.setCurrentIndex(int(s.value("ui/interval_index", self.interval.currentIndex())))

        # Dates
        start_iso = s.value("ui/start_date", None)
        end_iso = s.value("ui/end_date", None)
        if start_iso:
            d = QDate.fromString(start_iso, "yyyy-MM-dd")
            if d.isValid():
                self.start.setDate(d)
        if end_iso:
            d = QDate.fromString(end_iso, "yyyy-MM-dd")
            if d.isValid():
                self.end.setDate(d)

        # Checkboxes
        self.actions.setChecked(s.value("ui/include_actions", "true") == "true")
        self.auto_adjust.setChecked(s.value("ui/auto_adjust", "false") == "true")

        # Ensure UI enable/disable matches mode
        self.update_mode_ui()

    def save_settings(self):
        s = self.settings

        # Window geometry
        s.setValue("window/geometry", self.saveGeometry())

        # Text fields
        s.setValue("ui/tickers", self.tickers.text())
        s.setValue("ui/out_dir", self.out_dir.text())

        # Combos
        s.setValue("ui/mode_index", self.mode.currentIndex())
        s.setValue("ui/period_index", self.period.currentIndex())
        s.setValue("ui/interval_index", self.interval.currentIndex())

        # Dates
        s.setValue("ui/start_date", self.start.date().toString("yyyy-MM-dd"))
        s.setValue("ui/end_date", self.end.date().toString("yyyy-MM-dd"))

        # Checkboxes (store as "true"/"false" for simplicity)
        s.setValue("ui/include_actions", "true" if self.actions.isChecked() else "false")
        s.setValue("ui/auto_adjust", "true" if self.auto_adjust.isChecked() else "false")

    def closeEvent(self, event):
        # Final save on exit
        try:
            self.save_settings()
        except Exception:
            pass
        super().closeEvent(event)


    def log_line(self, s: str) -> None:
        self.log.append(s)
        self.log.ensureCursorVisible()

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.out_dir.text())
        if d:
            self.out_dir.setText(d)

    def update_mode_ui(self):
        mode_text = self.mode.currentText()
        is_range = mode_text.startswith("Date range")
        is_period = mode_text.startswith("Duration")

        self.start.setEnabled(is_range)
        self.end.setEnabled(is_range)
        self.period.setEnabled(is_period)

    def download(self):
        raw = self.tickers.text().strip()
        if not raw:
            QMessageBox.warning(self, "Missing tickers", "Please enter at least one ticker.")
            return

        # Allow comma/space/newline separation
        tickers = [t for t in raw.replace("\n", " ").replace(",", " ").split(" ") if t.strip()]
        if not tickers:
            QMessageBox.warning(self, "Invalid tickers", "Could not parse any tickers.")
            return

        interval = self.interval.currentText()

        mode_text = self.mode.currentText()
        if mode_text.startswith("Date range"):
            mode = "range"
        elif mode_text.startswith("Duration"):
            mode = "period"
        else:
            mode = "max"

        start_str = self.start.date().toString("yyyy-MM-dd")
        end_str = self.end.date().toString("yyyy-MM-dd")

        if mode == "range" and self.start.date() >= self.end.date():
            QMessageBox.warning(self, "Invalid dates", "Start date must be before end date.")
            return

        period = None
        if mode == "period":
            p = self.period.currentText()
            # If user picks "max" in period mode, treat it as max mode
            if p == "max":
                mode = "max"
            else:
                period = p

        cfg = DownloadConfig(
            tickers=tickers,
            interval=interval,
            include_actions=self.actions.isChecked(),
            auto_adjust=self.auto_adjust.isChecked(),
            out_dir=Path(self.out_dir.text()).expanduser(),
            mode=mode,
            start=start_str if mode == "range" else None,
            end=end_str if mode == "range" else None,
            period=period,
        )

        self.btn_download.setEnabled(False)
        try:
            fetch_and_save_csv(cfg, self.log_line)
        finally:
            self.btn_download.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    w = HimadaApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
