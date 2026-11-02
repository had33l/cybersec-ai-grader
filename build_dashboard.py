"""Convenience wrapper: python scripts/build_dashboard.py"""
from harness.dashboard import build

if __name__ == "__main__":
    out = build()
    print(f"wrote {out}")
