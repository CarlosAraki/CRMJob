"""
Módulo de Alertas - Bot do Telegram.
Envia avisos quando vagas mapeadas há mais de 2 dias ainda não tiveram currículo enviado.
"""

import asyncio
import streamlit as st

from database import (
    obter_config,
    salvar_config,
    listar_vagas_mapeadas_antigas,
)

CHAVE_TOKEN = "telegram_bot_token"
CHAVE_CHAT_ID = "telegram_chat_id"
DIAS_ALERTA = 2


def _enviar_mensagem_telegram(
    token: str, chat_id: str, texto: str, usar_markdown: bool = False
) -> tuple[bool, str]:
    """
    Envia mensagem via Telegram Bot API.
    Retorna (sucesso, mensagem_erro).
    Por padrão usa texto simples (Markdown desativado) para evitar erros com caracteres especiais.
    """
    try:
        from telegram import Bot

        # Limpa chat_id (remove espaços e caracteres não numéricos para IDs de usuário)
        chat_id_limpo = "".join(c for c in str(chat_id).strip() if c.isdigit() or c == "-")
        if not chat_id_limpo:
            return False, "Chat ID inválido. Use apenas números."

        async def _send():
            bot = Bot(token=token.strip())
            kwargs = {"chat_id": chat_id_limpo, "text": texto}
            if usar_markdown:
                kwargs["parse_mode"] = "Markdown"
            await bot.send_message(**kwargs)

        asyncio.run(_send())
        return True, ""
    except Exception as e:
        return False, str(e)


def verificar_e_enviar_alertas() -> tuple[int, list[str]]:
    """
    Verifica vagas mapeadas há mais de 2 dias e envia alertas no Telegram.
    Retorna (quantidade_enviada, lista_de_erros).
    """
    token = obter_config(CHAVE_TOKEN)
    chat_id = obter_config(CHAVE_CHAT_ID)

    if not token or not chat_id:
        return 0, ["Configure o Bot Token e Chat ID nas configurações acima."]

    vagas = listar_vagas_mapeadas_antigas(dias=DIAS_ALERTA)
    erros = []
    enviados = 0

    for vaga in vagas:
        cargo = vaga.get("cargo", "Vaga")
        empresa = vaga.get("empresa", "Empresa")
        link = (vaga.get("link") or "").strip()
        plataforma = vaga.get("plataforma") or ""
        data_mapeada = (vaga.get("criado_em") or "")[:10]
        data_limite = vaga.get("data_limite") or ""
        status = vaga.get("status", "")

        # Motivo do alerta
        if data_limite and status not in ("Rejeitada",):
            motivo = f"📅 Data limite em {data_limite}"
        else:
            motivo = f"📅 Mapeada desde {data_mapeada} — ainda sem aplicação"

        msg = (
            f"⚠️ Alerta CRM Busca de Emprego\n\n"
            f"{cargo} na {empresa}\n"
            f"Status: {status}\n"
            f"{motivo}\n"
        )
        if plataforma:
            msg += f"📋 Plataforma: {plataforma}\n"
        if link:
            msg += f"\n🔗 Link da vaga:\n{link}"
        else:
            msg += "\nAbra o CRM para ver os detalhes."

        ok, err = _enviar_mensagem_telegram(token, chat_id, msg, usar_markdown=False)
        if ok:
            enviados += 1
        else:
            erros.append(f"{vaga['empresa']} - {vaga['cargo']}: {err}")

    return enviados, erros


def render():
    """Renderiza o módulo de Alertas Telegram."""
    st.title("Alertas via Telegram")
    st.caption(
        "Configure seu bot e receba avisos quando: vagas Mapeada/Em Adaptação há mais de 2 dias "
        "sem envio, ou quando houver data limite nos próximos 3 dias."
    )

    st.divider()
    st.subheader("Configuração")

    with st.form("form_telegram_config"):
        token_atual = obter_config(CHAVE_TOKEN) or ""
        chat_id_atual = obter_config(CHAVE_CHAT_ID) or ""

        token = st.text_input(
            "TELEGRAM_BOT_TOKEN",
            value=token_atual,
            type="password",
            placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            help="Crie um bot com @BotFather, copie o token. Depois envie /start ao seu bot.",
        )
        chat_id = st.text_input(
            "CHAT_ID",
            value=chat_id_atual,
            placeholder="123456789",
            help="Obtenha em @userinfobot. IMPORTANTE: envie /start ao SEU bot antes de receber mensagens.",
        )

        if st.form_submit_button("Salvar configuração"):
            if token.strip() and chat_id.strip():
                chat_id_limpo = "".join(c for c in chat_id.strip() if c.isdigit() or c == "-")
                if not chat_id_limpo:
                    st.error("Chat ID deve conter apenas números.")
                else:
                    salvar_config(CHAVE_TOKEN, token.strip())
                    salvar_config(CHAVE_CHAT_ID, chat_id_limpo)
                    st.success("Configuração salva com sucesso!")
                    st.rerun()
            else:
                st.error("Preencha Token e Chat ID.")

    st.divider()
    st.subheader("Verificar e enviar alertas")

    vagas_pendentes = listar_vagas_mapeadas_antigas(dias=DIAS_ALERTA)

    st.info(
        "💡 **Importante:** Envie /start para o seu bot no Telegram antes de testar. "
        "O bot só pode enviar mensagens após você iniciar a conversa."
    )

    if st.button("📤 Enviar mensagem de teste", key="btn_testar_telegram"):
        token = obter_config(CHAVE_TOKEN)
        chat_id = obter_config(CHAVE_CHAT_ID)
        if not token or not chat_id:
            st.error("Configure Token e Chat ID acima antes de testar.")
        else:
            ok, err = _enviar_mensagem_telegram(
                token, chat_id,
                "✅ Teste do CRM Busca de Emprego: sua configuração está funcionando!",
                usar_markdown=False,
            )
            if ok:
                st.success("Mensagem de teste enviada! Verifique seu Telegram.")
            else:
                st.error(f"Erro ao enviar: {err}")

    st.divider()

    if vagas_pendentes:
        st.warning(
            f"Encontradas **{len(vagas_pendentes)}** vaga(s) para alerta "
            f"(mapeadas há 2+ dias sem envio ou com data limite próxima):"
        )
        for v in vagas_pendentes:
            info = v.get("criado_em", "")[:10]
            if v.get("data_limite"):
                info = f"limite {v['data_limite']}"
            st.markdown(f"- **{v['cargo']}** @ {v['empresa']} ({v['status']}) — {info}")
    else:
        st.info("Nenhuma vaga pendente de alerta no momento.")

    if st.button("Enviar alertas agora", type="primary", key="btn_enviar_alertas"):
        enviados, erros = verificar_e_enviar_alertas()

        if enviados > 0:
            st.success(f"✅ {enviados} alerta(s) enviado(s) com sucesso!")
        if erros:
            for e in erros:
                st.error(f"❌ {e}")
