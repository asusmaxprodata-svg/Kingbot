
import streamlit as st
from datetime import datetime
from st_utils import global_cfg, mode_cfg, tail_log

st.set_page_config(page_title="kang_bot • Dashboard", layout="wide")

g = global_cfg()
st.markdown('<style>'+open("app_streamlit/styles.css").read()+'</style>', unsafe_allow_html=True)
st.title("🤖 kang_bot — Dashboard")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Status", "RUN" if g.get("running", True) else "PAUSE")
col2.metric("Mode", g.get("mode","scalping").upper())
col3.metric("Pair", g.get("symbol","BTCUSDT"))
col4.metric("Env", "TESTNET" if g.get("testnet", True) else "REAL")

with st.expander("⚙️ Config Ringkas", expanded=False):
    st.json(g)

st.subheader("📜 Log (tail)")
st.code(tail_log(), language="log")
