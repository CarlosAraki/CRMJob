"""
Módulo 1: CRM - Funil de Vagas (Kanban/Tabela interativa).
"""

import streamlit as st
from datetime import datetime

from database import (
    init_db,
    listar_vagas,
    obter_vaga,
    inserir_vaga,
    atualizar_vaga,
    excluir_vaga,
)
from config import STATUS_VAGAS


def render():
    """Renderiza o módulo CRM."""
    st.title("Funil de Vagas")
    st.caption("Gerencie suas oportunidades de emprego em um fluxo visual")

    # Filtros, ordenação e visualização
    with st.expander("🔍 Filtros e Ordenação", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            filtro_status = st.selectbox(
                "Status",
                options=["Todos"] + STATUS_VAGAS,
                key="crm_filtro",
            )
        with c2:
            filtro_empresa = st.text_input(
                "Empresa (busca parcial)",
                placeholder="Ex: Gupy",
                key="crm_filtro_empresa",
            )
        with c3:
            filtro_plataforma = st.text_input(
                "Plataforma (busca parcial)",
                placeholder="Ex: Greenhouse",
                key="crm_filtro_plat",
            )
        with c4:
            opt_ordenar = st.selectbox(
                "Ordenar por",
                options=[
                    ("Data limite (mais urgente)", "data_limite", "asc"),
                    ("Empresa A–Z", "empresa", "asc"),
                    ("Recém adicionadas", "criado_em", "desc"),
                ],
                format_func=lambda x: x[0],
                key="crm_ordenar",
            )
            ordenar_por = opt_ordenar[1]
            ordem = opt_ordenar[2]

    col_vis, _ = st.columns([1, 3])
    with col_vis:
        modo_visual = st.radio(
            "Visualização",
            options=["Tabela", "Kanban"],
            horizontal=True,
            key="crm_modo",
        )

    # Botões de ação
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Nova Vaga", key="btn_nova_vaga"):
            st.session_state["crm_mostrar_form"] = True
    with col_btn2:
        if st.button("📥 Importar por URL", key="btn_importar_url"):
            st.session_state["navegar_para"] = "importador_urls"
            st.rerun()

    if st.session_state.get("crm_mostrar_form", False):
        render_form_nova_vaga()
        return

    # Edição de vaga
    vaga_editando = st.session_state.get("crm_editar_vaga_id")
    if vaga_editando:
        render_editar_vaga(vaga_editando)
        return

    # Listagem
    vagas = listar_vagas(
        filtro_status=filtro_status if filtro_status != "Todos" else None,
        filtro_empresa=filtro_empresa or None,
        filtro_plataforma=filtro_plataforma or None,
        ordenar_por=ordenar_por,
        ordem=ordem,
    )

    if not vagas:
        st.info("Nenhuma vaga cadastrada. Clique em **Nova Vaga** para começar.")
        return

    if modo_visual == "Kanban":
        render_kanban(vagas)
    else:
        render_tabela(vagas)


def render_form_nova_vaga():
    """Formulário para cadastrar nova vaga."""
    st.subheader("Cadastrar Nova Vaga")
    with st.form("form_nova_vaga", clear_on_submit=True):
        link = st.text_input("Link da vaga", placeholder="https://...")
        empresa = st.text_input("Nome da empresa *", placeholder="Ex: HealthTech Brasil")
        cargo = st.text_input("Cargo *", placeholder="Ex: CTO")
        plataforma = st.text_input("Plataforma (opcional)", placeholder="Ex: Gupy, Greenhouse, Workday")
        data_limite = st.date_input("Data limite de envio")
        descricao = st.text_area(
            "Descrição da vaga",
            placeholder="Cole aqui o texto completo da descrição da vaga...",
            height=200,
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Salvar"):
                if empresa and cargo:
                    vaga_id = inserir_vaga(
                        link=link,
                        empresa=empresa.strip(),
                        cargo=cargo.strip(),
                        data_limite=data_limite.isoformat() if data_limite else None,
                        descricao=descricao.strip() if descricao else "",
                        plataforma=plataforma.strip() if plataforma else None,
                    )
                    st.success(f"Vaga cadastrada com sucesso! (ID: {vaga_id})")
                    st.session_state["crm_mostrar_form"] = False
                    st.rerun()
                else:
                    st.error("Empresa e Cargo são obrigatórios.")

        with col2:
            if st.form_submit_button("Cancelar"):
                st.session_state["crm_mostrar_form"] = False
                st.rerun()


def render_editar_vaga(vaga_id: int):
    """Formulário para editar vaga existente."""
    vaga = obter_vaga(vaga_id)
    if not vaga:
        st.error("Vaga não encontrada.")
        st.session_state.pop("crm_editar_vaga_id", None)
        st.rerun()
        return

    st.subheader(f"Editar: {vaga['cargo']} @ {vaga['empresa']}")

    with st.form("form_editar_vaga"):
        link = st.text_input("Link", value=vaga["link"] or "")
        empresa = st.text_input("Empresa *", value=vaga["empresa"])
        cargo = st.text_input("Cargo *", value=vaga["cargo"])
        data_limite_str = vaga["data_limite"]
        try:
            data_limite_val = (
                datetime.strptime(data_limite_str, "%Y-%m-%d").date()
                if data_limite_str
                else None
            )
        except (ValueError, TypeError):
            data_limite_val = None
        data_limite = st.date_input("Data limite", value=data_limite_val)
        descricao = st.text_area("Descrição", value=vaga["descricao"] or "", height=150)
        plataforma = st.text_input("Plataforma", value=vaga.get("plataforma") or "")
        status = st.selectbox("Status", STATUS_VAGAS, index=STATUS_VAGAS.index(vaga["status"]))

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Salvar"):
                atualizar_vaga(
                    vaga_id,
                    link=link or None,
                    empresa=empresa,
                    cargo=cargo,
                    data_limite=data_limite.isoformat() if data_limite else None,
                    descricao=descricao,
                    status=status,
                    plataforma=plataforma.strip() or None,
                )
                st.success("Vaga atualizada!")
                st.session_state.pop("crm_editar_vaga_id", None)
                st.rerun()

        with col2:
            if st.form_submit_button("Cancelar"):
                st.session_state.pop("crm_editar_vaga_id", None)
                st.rerun()


def render_tabela(vagas: list):
    """Renderiza a lista de vagas em formato tabela com cores por status."""
    for v in vagas:
        cor = CORES_STATUS.get(v["status"], "#f5f5f5")
        with st.container():
            col_status, col_info, col_acoes = st.columns([1, 4, 2])
            with col_status:
                novo_status = st.selectbox(
                    "Status",
                    STATUS_VAGAS,
                    index=STATUS_VAGAS.index(v["status"]),
                    key=f"status_{v['id']}",
                    label_visibility="collapsed",
                )
                if novo_status != v["status"]:
                    atualizar_vaga(v["id"], status=novo_status)
                    st.rerun()
                st.markdown(
                    f'<span style="background:{cor}; padding:3px 8px; border-radius:6px; '
                    f'font-size:0.75em; display:inline-block; margin-top:4px;">{v["status"]}</span>',
                    unsafe_allow_html=True,
                )

            with col_info:
                data_lim = f" até {v['data_limite']}" if v.get("data_limite") else ""
                plat = f" ({v['plataforma']})" if v.get("plataforma") else ""
                st.markdown(
                    f"**{v['cargo']}** @ *{v['empresa']}*{data_lim}{plat}"
                )
                if v.get("link"):
                    st.caption(f"[Ver vaga]({v['link']})")

            with col_acoes:
                if st.button("📝 Editar", key=f"edit_{v['id']}"):
                    st.session_state["crm_editar_vaga_id"] = v["id"]
                    st.rerun()
                if st.button("📋 Prompt", key=f"prompt_{v['id']}"):
                    st.session_state["gerador_vaga_id"] = v["id"]
                    st.session_state["navegar_para"] = "gerador_prompts"
                    st.rerun()
                if st.button("🗑️", key=f"del_{v['id']}"):
                    excluir_vaga(v["id"])
                    st.rerun()

            st.divider()


# Cores por status para visualização no Kanban
CORES_STATUS = {
    "Mapeada": "#e3f2fd",      # azul claro
    "Em Adaptação": "#fff3e0",  # laranja claro
    "Currículo Enviado": "#e8f5e9",  # verde claro
    "Entrevista": "#f3e5f5",   # roxo claro
    "Proposta": "#e8eaf6",     # índigo claro
    "Rejeitada": "#ffebee",    # vermelho claro
}


def render_kanban(vagas: list):
    """Renderiza o Kanban com colunas por status e cores visuais."""
    colunas = st.columns(len(STATUS_VAGAS))

    for i, status in enumerate(STATUS_VAGAS):
        with colunas[i]:
            cor = CORES_STATUS.get(status, "#f5f5f5")
            st.markdown(
                f'<div style="background:{cor}; padding:8px 12px; border-radius:8px; margin-bottom:8px; '
                f'border-left:4px solid {cor}; font-weight:bold;">{status}</div>',
                unsafe_allow_html=True,
            )
            vagas_status = [v for v in vagas if v["status"] == status]
            for v in vagas_status:
                with st.container():
                    st.markdown(f"**{v['cargo']}**")
                    plat = f" • {v['plataforma']}" if v.get("plataforma") else ""
                    st.caption(f"{v['empresa']}{plat}")
                    if v.get("data_limite"):
                        st.caption(f"📅 {v['data_limite']}")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("📝", key=f"k_edit_{i}_{v['id']}", help="Editar"):
                            st.session_state["crm_editar_vaga_id"] = v["id"]
                            st.rerun()
                    with col_b:
                        if st.button("📋", key=f"k_prompt_{i}_{v['id']}", help="Gerar Prompt"):
                            st.session_state["gerador_vaga_id"] = v["id"]
                            st.session_state["navegar_para"] = "gerador_prompts"
                            st.rerun()

                    opcoes = ["-- Mover --"] + [s for s in STATUS_VAGAS if s != status]
                    novo = st.selectbox(
                        "Mover para",
                        opcoes,
                        key=f"k_move_{i}_{v['id']}",
                        label_visibility="collapsed",
                    )
                    if novo and novo != "-- Mover --":
                        atualizar_vaga(v["id"], status=novo)
                        st.rerun()

                    st.divider()
