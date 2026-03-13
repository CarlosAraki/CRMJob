"""
CRM Pessoal de Busca de Emprego
Aplicação principal com menu lateral e módulos.
"""

import streamlit as st

from database import init_db
from modules.crm import render as render_crm
from modules.gerador_prompts import render as render_gerador_prompts
from modules.alertas_telegram import render as render_alertas_telegram
from modules.busca_ativa import render as render_busca_ativa
from modules.atalhos_busca import render as render_atalhos_busca
from modules.importador_urls import render as render_importador_urls


# Configuração da página
st.set_page_config(
    page_title="CRM Busca de Emprego",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inicialização do banco
init_db()

# Navegação programática: processar antes do menu (evita erro ao modificar key do widget)
if st.session_state.get("navegar_para"):
    st.session_state["menu_modulo"] = st.session_state.pop("navegar_para")

# Menu lateral
with st.sidebar:
    st.title("💼 CRM Busca de Emprego")
    st.divider()

    modulo = st.radio(
        "Módulos",
        options=["crm", "gerador_prompts", "alertas_telegram", "busca_ativa", "atalhos_busca", "importador_urls"],
        format_func=lambda x: {
            "crm": "📋 Funil de Vagas (CRM)",
            "gerador_prompts": "✨ Gerador de Prompts",
            "alertas_telegram": "🔔 Alertas Telegram",
            "busca_ativa": "🔍 Busca Ativa",
            "atalhos_busca": "🔗 Atalhos de Busca",
            "importador_urls": "📥 Importar por URL",
        }[x],
        key="menu_modulo",
    )

    st.divider()

# Roteamento de módulos
if modulo == "crm":
    st.session_state["modulo_atual"] = "crm"
    render_crm()
elif modulo == "gerador_prompts":
    st.session_state["modulo_atual"] = "gerador_prompts"
    render_gerador_prompts()
elif modulo == "alertas_telegram":
    st.session_state["modulo_atual"] = "alertas_telegram"
    render_alertas_telegram()
elif modulo == "busca_ativa":
    st.session_state["modulo_atual"] = "busca_ativa"
    render_busca_ativa()
elif modulo == "atalhos_busca":
    st.session_state["modulo_atual"] = "atalhos_busca"
    render_atalhos_busca()
elif modulo == "importador_urls":
    st.session_state["modulo_atual"] = "importador_urls"
    render_importador_urls()
