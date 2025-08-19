
import streamlit as st, subprocess, sys, os, platform
from st_utils import global_cfg, DATA_ROOT

st.set_page_config(page_title="Tuning Center", layout="centered")
st.title("🧪 Tuning Center (Optuna)")

g = global_cfg()
mode = st.selectbox("Mode", options=["scalping","hybrid","swing"], index=0)
pair = st.text_input("Pair", value=g.get("symbol","BTCUSDT"))
tf = st.selectbox("Timeframe", options=["5m","15m","1h"], index=0)
trials = st.slider("Trials", min_value=50, max_value=600, value=150, step=50)

csv = DATA_ROOT / f"{pair}_{tf}.csv"
st.caption(f"CSV: {csv}")

run = st.button("▶️ Jalankan Tuning")
if run:
    cmd = [sys.executable, "tools/tune_xgb_optuna.py", "--mode", mode, "--csv", str(csv), "--timeframe", tf, "--trials", str(trials), "--confidence_target", "0.75"]
    st.write("Menjalankan:", " ".join(cmd))
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=3600)
        st.success("Tuning selesai.")
        st.code(out.decode("utf-8")[:4000])
    except subprocess.CalledProcessError as e:
        st.error("Tuning gagal.")
        st.code(e.output.decode("utf-8") if e.output else str(e))
    except Exception as e:
        st.error(str(e))


st.divider()
st.subheader("Apply Best Config")
if st.button("✅ Apply ke Active Config"):
    import shutil
    cfg_src_pair = Path(f"config/{mode}__{pair}_best.json")
    cfg_src_mode = Path(f"config/{mode}_best.json")
    target = Path(f"config/{mode}.json")
    try:
        if cfg_src_pair.exists():
            shutil.copyfile(cfg_src_pair, target)
            st.success(f"Applied: {cfg_src_pair} → {target}")
        elif cfg_src_mode.exists():
            shutil.copyfile(cfg_src_mode, target)
            st.success(f"Applied: {cfg_src_mode} → {target}")
        else:
            st.warning("Best config belum ditemukan. Jalankan tuning dahulu.")
    except Exception as e:
        st.error(str(e))


st.subheader("One-click: Tune & Apply")
if st.button("🚀 Tune & Apply Best"):
    import subprocess, sys, shutil
    cmd = [sys.executable, "tools/tune_xgb_optuna.py", "--mode", mode, "--csv", str(csv), "--timeframe", tf, "--trials", str(trials), "--confidence_target", "0.75"]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=7200)
        st.success("Tuning selesai. Menerapkan best config...")
        cfg_src_pair = Path(f"config/{mode}__{pair}_best.json")
        cfg_src_mode = Path(f"config/{mode}_best.json")
        target = Path(f"config/{mode}.json")
        if cfg_src_pair.exists():
            shutil.copyfile(cfg_src_pair, target)
            st.success(f"Applied: {cfg_src_pair} → {target}")
        elif cfg_src_mode.exists():
            shutil.copyfile(cfg_src_mode, target)
            st.success(f"Applied: {cfg_src_mode} → {target}")
        else:
            st.warning("Best config belum ditemukan setelah tuning.")
        st.code(out.decode("utf-8")[:4000])
    except subprocess.CalledProcessError as e:
        st.error("Tuning gagal.")
        st.code(e.output.decode("utf-8") if e.output else str(e))
    except Exception as e:
        st.error(str(e))
