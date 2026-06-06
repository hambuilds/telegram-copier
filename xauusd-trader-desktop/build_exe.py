# build_exe.py
# Bundles trader_app.py into a single standalone executable via PyInstaller.
# Run:  python build_exe.py
# Output: dist/XAUUSDTrader  (Linux/macOS)  or  dist/XAUUSDTrader.exe  (Windows)


def build() -> None:
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        "trader_app.py",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name",
        "XAUUSDTrader",
        "--hidden-import",
        "config_store",
        "--hidden-import",
        "signal_parser",
        "--hidden-import",
        "mt5_engine",
        "--hidden-import",
        "telegram_bot",
    ])


if __name__ == "__main__":
    build()