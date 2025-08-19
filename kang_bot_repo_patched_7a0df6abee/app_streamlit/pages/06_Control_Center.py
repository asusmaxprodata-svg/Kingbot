
import streamlit as st, hashlib, json
from pathlib import Path
from st_utils import global_cfg, set_global_key

SEC_PATH = Path("config/security.json")

def load_sec():
    try:
        return json.loads(SEC_PATH.read_text())
    except Exception:
        return {}

def save_sec(obj):
    SEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEC_PATH.write_text(json.dumps(obj, indent=2))

def pin_hash(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()

st.set_page_config(page_title="Control Center", layout="centered")
st.title("🧭 Control Center")

g = global_cfg()
sec = load_sec()

st.subheader("Bot State")
col1, col2 = st.columns(2)
with col1:
    st.metric("Running", "YES" if g.get("running", True) else "NO")
with col2:
    st.metric("Env", "TESTNET" if g.get("testnet", True) else "REAL")

# RUN/PAUSE buttons
st.write("### Run / Pause")
run_req = st.button("▶️ RUN")
pause_req = st.button("⏸️ PAUSE")

# Multi-account profile
st.write("### Profile (Testnet / Real)")
profiles = ["testnet","real"]
sel = st.selectbox("Active Profile", options=profiles, index=0 if g.get("testnet", True) else 1)

# PIN management
st.write("### PIN Protection (untuk aksi Real)")
pin_set = "pin_hash" in sec and sec["pin_hash"]
pin_input = st.text_input("Masukkan PIN (wajib untuk REAL actions)", type="password")
if not pin_set:
    new_pin = st.text_input("Set PIN baru (minimal 4 digit)", type="password")
    if st.button("Set PIN") and len(new_pin)>=4:
        sec["pin_hash"] = pin_hash(new_pin)
        save_sec(sec)
        st.success("PIN diset.")
else:
    if st.button("Reset PIN"):
        sec.pop("pin_hash", None)
        save_sec(sec)
        st.success("PIN dihapus. Set ulang PIN baru.")

# Apply actions
def verify_pin_if_real():
    if sel == "real" or (not g.get("testnet", True)):
        if not sec.get("pin_hash"):
            st.error("PIN belum diset.")
            return False
        if pin_hash(pin_input) != sec.get("pin_hash"):
            st.error("PIN salah.")
            return False
    return True

if run_req:
    if verify_pin_if_real():
        set_global_key("running", True)
        st.success("Bot di-set RUN.")

if pause_req:
    # Pause boleh tanpa PIN
    set_global_key("running", False)
    st.warning("Bot di-set PAUSE.")

if st.button("Apply Profile"):
    if sel == "real":
        if verify_pin_if_real():
            set_global_key("testnet", False)
            set_global_key("active_profile", "real")
            st.success("Switch ke REAL.")
    else:
        set_global_key("testnet", True)
        set_global_key("active_profile", "testnet")
        st.info("Switch ke TESTNET.")
