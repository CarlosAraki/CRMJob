"""
Módulo de Currículos - Versionamento de PDFs e anexos por vaga.
Permite cadastrar versões de currículo, vincular à vaga e anexar:
respostas específicas, cartas de apresentação e recomendações.
"""

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from database import (
    listar_curriculums,
    inserir_curriculum,
    obter_curriculum,
    excluir_curriculum,
    listar_documentos_vaga,
    vincular_documento_vaga,
    excluir_documento_vaga,
    obter_vaga,
    listar_vagas,
    TIPOS_DOCUMENTO,
)

UPLOADS_DIR = Path(os.environ.get("UPLOADS_PATH", str(Path(__file__).parent.parent / "uploads")))
CURRICULUMS_DIR = UPLOADS_DIR / "curriculums"
ANEXOS_DIR = UPLOADS_DIR / "anexos"

LABELS_TIPO = {
    "curriculum": "Currículo (PDF enviado)",
    "resposta_vaga": "Resposta específica da vaga",
    "carta_apresentacao": "Carta de apresentação",
    "carta_recomendacao": "Carta de recomendação",
}


def _garantir_dirs():
    """Garante que os diretórios de upload existem."""
    CURRICULUMS_DIR.mkdir(parents=True, exist_ok=True)
    ANEXOS_DIR.mkdir(parents=True, exist_ok=True)


def _salvar_arquivo(uploaded_file, subdir: Path) -> str:
    """Salva arquivo do upload e retorna caminho relativo."""
    _garantir_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome = uploaded_file.name.replace(" ", "_")
    base, ext = os.path.splitext(nome)
    if not ext.lower() == ".pdf":
        ext = ".pdf"
    filename = f"{base}_{timestamp}{ext}"
    path = subdir / filename
    path.write_bytes(uploaded_file.getvalue())
    return str(path.relative_to(UPLOADS_DIR))


def _path_absoluto(caminho_rel: str) -> Path:
    """Converte caminho relativo em absoluto."""
    return UPLOADS_DIR / caminho_rel


def render():
    """Renderiza o módulo de Currículos."""
    st.title("📄 Currículos e Documentos")
    st.caption(
        "Versionamento de currículos em PDF e anexos por vaga: "
        "respostas específicas, cartas de apresentação e recomendações."
    )

    vaga_id = st.session_state.get("curriculums_vaga_id")

    if st.button("← Voltar ao CRM", key="curric_back"):
        st.session_state.pop("curriculums_vaga_id", None)
        st.session_state["navegar_para"] = "crm"
        st.rerun()

    st.divider()

    # === Seção 1: Meus currículos (versionamento) ===
    st.subheader("📑 Meus currículos (versionamento)")
    st.caption("Cadastre versões do seu currículo em PDF para vincular às vagas.")

    curriculums = listar_curriculums()

    with st.expander("➕ Nova versão de currículo", expanded=False):
        with st.form("form_novo_curriculum"):
            nome = st.text_input("Nome", value="CV Principal", placeholder="Ex: CV Principal, CV Executivo")
            versao = st.text_input("Versão", placeholder="Ex: v1.2, Mar 2025")
            arquivo = st.file_uploader("PDF do currículo", type=["pdf"], key="curric_upload")
            if st.form_submit_button("Salvar"):
                if nome and versao and arquivo:
                    _garantir_dirs()
                    caminho = _salvar_arquivo(arquivo, CURRICULUMS_DIR)
                    inserir_curriculum(nome.strip(), versao.strip(), caminho)
                    st.success("Currículo cadastrado!")
                    st.rerun()
                else:
                    st.error("Preencha nome, versão e envie o PDF.")

    if curriculums:
        for c in curriculums:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                path_full = _path_absoluto(c["caminho_arquivo"])
                if path_full.exists():
                    with open(path_full, "rb") as f:
                        st.download_button(
                            f"📥 {c['nome']} — {c['versao']}",
                            data=f.read(),
                            file_name=path_full.name,
                            mime="application/pdf",
                            key=f"dl_curric_{c['id']}",
                        )
                else:
                    st.caption(f"⚠️ {c['nome']} — {c['versao']} (arquivo não encontrado)")
            with col3:
                if st.button("🗑️", key=f"del_curric_{c['id']}", help="Excluir"):
                    excluir_curriculum(c["id"])
                    st.rerun()
            st.caption(f"  Cadastrado em {c['criado_em'][:10]}")
    else:
        st.info("Nenhum currículo cadastrado. Adicione a primeira versão acima.")

    st.divider()

    # === Seção 2: Vincular à vaga ===
    st.subheader("🔗 Documentos por vaga")
    st.caption("Selecione uma vaga e vincule currículo + anexos (respostas, cartas).")

    vagas = listar_vagas(filtro_status=None, excluir_rejeitadas=False)
    opcoes_vagas = [(f"{v['cargo']} @ {v['empresa']}", v["id"]) for v in vagas]

    if not opcoes_vagas:
        st.info("Cadastre vagas no CRM para vincular documentos.")
        return

    idx_inicial = 0
    if vaga_id:
        for i, (_, vid) in enumerate(opcoes_vagas):
            if vid == vaga_id:
                idx_inicial = i
                break
    vaga_selecionada = st.selectbox(
        "Vaga",
        options=opcoes_vagas,
        format_func=lambda x: x[0],
        index=idx_inicial,
        key="curric_select_vaga",
    )
    vaga_id_atual = vaga_selecionada[1]
    vaga = obter_vaga(vaga_id_atual)

    if vaga:
        docs = listar_documentos_vaga(vaga_id_atual)

        # Vincular currículo
        st.markdown("**Vincular currículo enviado**")
        if curriculums:
            opts = [(f"{c['nome']} — {c['versao']}", c["id"], f"{c['nome']} {c['versao']}") for c in curriculums]
            opt_sel = st.selectbox(
                "Currículo",
                options=[("— Não vincular novo —", None, None)] + opts,
                format_func=lambda x: x[0],
                key="curric_link_select",
            )
            curric_id = opt_sel[1] if opt_sel and opt_sel[1] else None
            nome_curric = (opt_sel[2] if len(opt_sel) > 2 and opt_sel[2] else "Currículo") if curric_id else ""
            if curric_id and st.button("Vincular currículo", key="btn_vinc_curric"):
                vincular_documento_vaga(
                    vaga_id_atual, "curriculum", nome_curric, curriculum_id=curric_id
                )
                st.success("Currículo vinculado!")
                st.rerun()
        else:
            st.caption("Cadastre um currículo acima para vincular.")

        # Upload de anexos
        st.markdown("**Anexos (respostas, cartas)**")
        with st.expander("➕ Adicionar anexo", expanded=False):
            with st.form("form_anexo"):
                tipo_anexo = st.selectbox(
                    "Tipo",
                    options=TIPOS_DOCUMENTO[1:],
                    format_func=lambda t: LABELS_TIPO.get(t, t),
                    key="anexo_tipo",
                )
                nome_anexo = st.text_input("Nome", placeholder="Ex: Resposta questões técnicas")
                arq = st.file_uploader("Arquivo (PDF)", type=["pdf"], key="anexo_upload")
                if st.form_submit_button("Adicionar"):
                    if nome_anexo and arq:
                        caminho = _salvar_arquivo(arq, ANEXOS_DIR)
                        vincular_documento_vaga(
                            vaga_id_atual, tipo_anexo, nome_anexo.strip(), caminho_arquivo=caminho
                        )
                        st.success("Anexo adicionado!")
                        st.rerun()
                    else:
                        st.error("Preencha nome e envie o arquivo.")

        # Lista de documentos vinculados
        st.markdown("**Documentos desta vaga**")
        if docs:
            for d in docs:
                tipo_label = LABELS_TIPO.get(d["tipo"], d["tipo"])
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    if d["curriculum_id"] and d.get("curriculum_nome"):
                        st.caption(f"📄 {tipo_label}: {d['curriculum_nome']} — {d.get('curriculum_versao', '')}")
                        path_c = obter_curriculum(d["curriculum_id"])
                        if path_c:
                            p = _path_absoluto(path_c["caminho_arquivo"])
                            if p.exists():
                                with open(p, "rb") as f:
                                    st.download_button("📥 Baixar", data=f.read(), file_name=p.name, mime="application/pdf", key=f"dl_doc_{d['id']}")
                    elif d["caminho_arquivo"]:
                        st.caption(f"📎 {tipo_label}: {d['nome']}")
                        p = _path_absoluto(d["caminho_arquivo"])
                        if p.exists():
                            with open(p, "rb") as f:
                                st.download_button("📥 Baixar", data=f.read(), file_name=p.name, mime="application/pdf", key=f"dl_doc_{d['id']}")
                with col_b:
                    if st.button("🗑️", key=f"del_doc_{d['id']}", help="Remover"):
                        excluir_documento_vaga(d["id"])
                        st.rerun()
        else:
            st.info("Nenhum documento vinculado a esta vaga ainda.")
