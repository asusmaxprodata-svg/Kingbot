import pandas as pd
import streamlit as st

def stat_card(title, value, help_text=None):
    st.markdown(
        f"""
        <div style="padding:14px;border-radius:14px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1)">
          <div style="font-size:12px;opacity:.7">{title}</div>
          <div style="font-size:24px;font-weight:700">{value}</div>
          {f'<div style="font-size:11px;opacity:.6">{help_text}</div>' if help_text else ''}
        </div>
        """, unsafe_allow_html=True
    )
