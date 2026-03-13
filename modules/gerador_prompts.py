"""
Módulo 2: Gerador de Prompts - Otimizador sem API.
Gera prompts estruturados para copiar e colar em IA web gratuita.
"""

import streamlit as st

try:
    import pyperclip
    PYPERCLIP_DISPONIVEL = True
except ImportError:
    PYPERCLIP_DISPONIVEL = False

from database import obter_vaga, atualizar_vaga
from config import PERFIL_PADRAO


PROMPT_TEMPLATE = """Atue como recrutador. Aqui está meu perfil:

[PERFIL]
{perfil}

Aqui está a vaga:

[VAGA]
Cargo: {cargo}
Empresa: {empresa}

Descrição da vaga:
{descricao}

---

Reescreva os 5 principais bullet points do meu currículo para dar match com essa vaga, sem inventar dados."""


def gerar_prompt(vaga: dict) -> str:
    """Gera o texto do prompt combinando perfil e vaga."""
    perfil = PERFIL_PADRAO["resumo_base"]
    return PROMPT_TEMPLATE.format(
        perfil=perfil,
        cargo=vaga["cargo"],
        empresa=vaga["empresa"],
        descricao=vaga["descricao"] or "(Descrição não fornecida)",
    )


def render():
    """Renderiza o módulo Gerador de Prompts."""
    st.title("Gerador de Prompts")
    st.caption(
        "Gere prompts otimizados para usar em IAs web gratuitas. "
        "Copie o prompt, cole no chat da IA e depois cole o resultado aqui."
    )

    vaga_id = st.session_state.get("gerador_vaga_id")

    if not vaga_id:
        st.info(
            "Selecione uma vaga no **CRM** e clique em **📋 Prompt** "
            "para gerar o prompt de adaptação de currículo."
        )
        if st.button("← Voltar ao CRM"):
            st.session_state["navegar_para"] = "crm"
            st.rerun()
        return

    vaga = obter_vaga(vaga_id)
    if not vaga:
        st.error("Vaga não encontrada.")
        st.session_state.pop("gerador_vaga_id", None)
        st.rerun()
        return

    # Cabeçalho da vaga
    st.subheader(f"{vaga['cargo']} @ {vaga['empresa']}")

    # Gerar prompt
    prompt_texto = gerar_prompt(vaga)

    st.markdown("### Prompt para copiar")
    st.text_area(
        "Texto do prompt (edite se desejar)",
        value=prompt_texto,
        height=300,
        key="gerador_prompt_edit",
    )

    # Botão Copiar
    col_copiar, col_voltar = st.columns(2)
    with col_copiar:
        if st.button("📋 Copiar Prompt", type="primary", key="btn_copiar_prompt"):
            texto = st.session_state.get("gerador_prompt_edit", prompt_texto)
            if PYPERCLIP_DISPONIVEL:
                try:
                    pyperclip.copy(texto)
                    st.success("Prompt copiado para a área de transferência!")
                except Exception as e:
                    st.warning(
                        f"Não foi possível copiar automaticamente. "
                        f"Selecione o texto acima e use Ctrl+C. Erro: {e}"
                    )
            else:
                st.info(
                    "Instale 'pyperclip' para copiar automaticamente: "
                    "pip install pyperclip. Por ora, selecione o texto e use Ctrl+C."
                )

    with col_voltar:
        if st.button("← Voltar ao CRM", key="btn_voltar_crm"):
            st.session_state.pop("gerador_vaga_id", None)
            st.session_state["navegar_para"] = "crm"
            st.rerun()

    st.divider()
    st.markdown("### Colar Resultado da IA")
    st.caption(
        "Após colar sua resposta no chat da IA e receber os bullet points "
        "adaptados, cole o resultado abaixo para salvar no CRM."
    )

    curriculo_adaptado = st.text_area(
        "Colar Resultado da IA",
        value=vaga.get("curriculo_adaptado") or "",
        height=250,
        placeholder="Cole aqui o texto que a IA retornou (os bullet points adaptados)...",
        key="gerador_resultado_ia",
    )

    if st.button("💾 Salvar Currículo Adaptado", key="btn_salvar_resultado"):
        atualizar_vaga(vaga_id, curriculo_adaptado=curriculo_adaptado.strip() or None)
        st.success("Currículo adaptado salvo com sucesso!")
