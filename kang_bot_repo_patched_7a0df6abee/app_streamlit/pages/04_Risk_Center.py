
import streamlit as st
from st_utils import global_cfg, set_global_key

st.set_page_config(page_title="Risk Center", layout="centered")
st.title("🛡️ Risk Center")

g = global_cfg()
max_dd = st.number_input("Max daily loss (%)", min_value=1.0, max_value=50.0, value=float(g.get("max_daily_loss_pct",10)), step=0.5)
max_open = st.number_input("Max open posisi (global)", min_value=1, max_value=10, value=int(g.get("max_open_positions",3)), step=1)
trailing = st.toggle("Trailing Dinamis AI", value=bool(g.get("trailing_ai", True)))
pause_on = st.toggle("Auto-pause saat cap loss tercapai", value=bool(g.get("auto_pause", True)))

if st.button("💾 Simpan Risk"):
    set_global_key("max_daily_loss_pct", float(max_dd))
    set_global_key("max_open_positions", int(max_open))
    set_global_key("trailing_ai", bool(trailing))
    set_global_key("auto_pause", bool(pause_on))
    st.success("Risk guard tersimpan.")
