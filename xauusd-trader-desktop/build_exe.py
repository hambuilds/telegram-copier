# build_exe.py
# Bundles trader_app.py into a single .exe via PyInstaller.
# Run: python build_exe.py


def build() -> None:
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        "--onefile",
        "--windowed",
        "--name",
        "XAUUSDTrader",
        "trader_app.py",
    ])


if __name__ == "__main__":
    build()