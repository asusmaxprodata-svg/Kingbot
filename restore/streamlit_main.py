# Auto-generated streamlit entrypoint (build 7a0df6abee)
# Tries app_streamlit/Home.py first, then streamlit_app/app.py
import os, sys, importlib

ROOT = os.path.dirname(os.path.abspath(__file__))
# Ensure local packages are importable
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

candidates = [
    ("app_streamlit.Home", "app_streamlit/Home.py"),
    ("streamlit_app.app", "streamlit_app/app.py"),
]

found = None
for modname, hint in candidates:
    try:
        importlib.import_module(modname)
        found = modname
        break
    except Exception:
        continue

if not found:
    import streamlit as st
    st.error("Tidak menemukan entrypoint Streamlit yang valid. Periksa folder app_streamlit/ atau streamlit_app/.")
else:
    # Re-run the selected module
    import runpy
    pkg, _, _ = found.partition(".")
    # Add candidate packages to sys.path for nested imports
    pkg_path = os.path.join(ROOT, pkg)
    if os.path.isdir(pkg_path) and pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)
    runpy.run_module(found, run_name="__main__")
