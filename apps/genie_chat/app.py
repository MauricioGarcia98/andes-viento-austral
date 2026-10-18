"""Andes Viento Austral · chat con los Genie Agents (Databricks App, Streamlit).

La App corre con el service principal de la App. scripts/deploy_genie.py --grant-app le da
permiso CAN_RUN sobre los spaces y SELECT/EXECUTE sobre el catálogo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient

sys.path.insert(0, str(Path(__file__).parent))
from genie_client import GenieClient  # noqa: E402

st.set_page_config(page_title="Andes · Genie", page_icon="🌬️", layout="wide")
w = WorkspaceClient()
PREFIX = os.environ.get("GENIE_TITLE_PREFIX", "Andes ·")


@st.cache_data(ttl=300)
def spaces() -> dict[str, str]:
    resp = w.api_client.do("GET", "/api/2.0/genie/spaces")
    return {s["title"]: s["space_id"] for s in resp.get("spaces", []) if s["title"].startswith(PREFIX)}


st.title("🌬️☀️ Andes Viento Austral · Preguntale a Genie")
available = spaces()
if not available:
    st.warning("No veo Genie Agents. Corré `python scripts/deploy_genie.py --grant-app andes-genie-chat`.")
    st.stop()
agent = st.sidebar.selectbox("Agent", list(available))
st.sidebar.caption("Cada área tiene su agent: Operación, Mantenimiento, Comercial y Finanzas.")
if st.sidebar.button("Nueva conversación"):
    st.session_state.pop("conv", None)
    st.session_state["history"] = []

st.session_state.setdefault("history", [])
for role, content in st.session_state["history"]:
    with st.chat_message(role):
        if isinstance(content, pd.DataFrame):
            st.dataframe(content, use_container_width=True)
        else:
            st.markdown(content)

if question := st.chat_input("Ej.: ¿Por qué Cañadón León generó menos en julio 2025?"):
    st.session_state["history"].append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("Genie está pensando..."):
        ans = GenieClient(w, available[agent]).ask(question, st.session_state.get("conv"))
        st.session_state["conv"] = ans.conversation_id
        text = ans.text or ans.description or ""
        if text:
            st.markdown(text)
            st.session_state["history"].append(("assistant", text))
        if ans.rows:
            df = pd.DataFrame(ans.rows, columns=ans.columns)
            st.dataframe(df, use_container_width=True)
            st.session_state["history"].append(("assistant", df))
        if ans.sql:
            with st.expander("Ver el SQL que generó Genie"):
                st.code(ans.sql, language="sql")
        if ans.suggested_questions:
            st.caption("Podés seguir con: " + " · ".join(ans.suggested_questions))
        if ans.error:
            st.error(ans.error)
