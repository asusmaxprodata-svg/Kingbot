
import streamlit as st
from st_utils import global_cfg, set_global_key

st.set_page_config(page_title="Controls", layout="centered")
st.title("🕹️ Controls")

g = global_cfg()
st.write("Mode & Pair")
col1, col2 = st.columns(2)
with col1:
    new_mode = st.selectbox("Mode", options=["scalping","hybrid","swing","adaptive"], index=["scalping","hybrid","swing","adaptive"].index(g.get("mode","scalping")))
with col2:
    new_pair = st.text_input("Pair aktif", value=g.get("symbol","BTCUSDT"))

st.write("Pair Selector")
auto = st.toggle("Auto Pair", value=g.get("auto_pairs", True))
interval = st.slider("Interval update pair (menit)", min_value=1, max_value=180, value=int(g.get("pair_update_interval_min",15)), step=1)

st.write("Leverage")
lev_opt = st.radio("Leverage mode", options=["auto","manual"], index=0 if str(g.get("leverage","auto")).startswith("auto") else 1, horizontal=True)
lev_val = st.select_slider("Leverage manual", options=[1,2,3,5,10,20,50,100], value=int(g.get("leverage",10)) if isinstance(g.get("leverage",10), int) else 10)

if st.button("💾 Simpan"):
    set_global_key("mode", new_mode)
    set_global_key("symbol", new_pair.upper())
    set_global_key("auto_pairs", bool(auto))
    set_global_key("pair_update_interval_min", int(interval))
    set_global_key("leverage", "auto" if lev_opt=="auto" else int(lev_val))
    st.success("Tersimpan. Bot akan membaca perubahan pada loop berikutnya.")
