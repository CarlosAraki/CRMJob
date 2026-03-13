"""
Módulo de Atalhos de Busca - Links diretos para as maiores plataformas de vagas no Brasil.
Otimizado para o perfil Carlos Araki (CTO, Head de TI, liderança estratégica).
Cada link abre a plataforma com busca pré-preenchida — faça login manualmente no site.
"""

import urllib.parse
import streamlit as st

from config import PERFIL_PADRAO

CARGOS = PERFIL_PADRAO["cargos_alvo"]
CARGOS_PRIORIDADE = PERFIL_PADRAO.get("cargos_prioridade", CARGOS[:4])
LOCALIZACOES = PERFIL_PADRAO["localizacao_busca"]


def _encodar(texto: str) -> str:
    """Codifica texto para URL."""
    return urllib.parse.quote(texto, safe="")


def _para_slug(texto: str) -> str:
    """Converte texto para slug URL-friendly."""
    replacements = {"ê": "e", "é": "e", "á": "a", "ã": "a", "ó": "o", "ç": "c", "í": "i", "ú": "u"}
    t = texto.lower().strip()
    for old, new in replacements.items():
        t = t.replace(old, new)
    return "-".join(t.split())


def _montar_links(cargo: str, local: str) -> dict[str, str]:
    """
    Monta URLs de busca para cada plataforma.
    Retorna dict {nome_plataforma: url}
    """
    cargo_enc = _encodar(cargo)
    local_enc = _encodar(local)
    cargo_slug = _para_slug(cargo)

    return {
        "LinkedIn Jobs": (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={cargo_enc}&location={local_enc}%2C%20Brasil"
        ),
        "Indeed Brasil": (
            f"https://br.indeed.com/empregos?q={cargo_enc}&l={local_enc}"
        ),
        "Catho": (
            f"https://www.catho.com.br/vagas/{cargo_slug}/?q={cargo_enc}"
        ),
        "Vagas.com": (
            f"https://www.vagas.com.br/vagas-de-{cargo_slug}"
        ),
        "InfoJobs": (
            f"https://www.infojobs.com.br/vagas-de-{cargo_slug}.aspx"
        ),
        "Trabalha Brasil": (
            f"https://www.trabalhabrasil.com.br/vagas?palavra_chave={cargo_enc}"
        ),
        "GeekHunter (TI)": (
            f"https://www.geekhunter.com.br/vagas?search={cargo_enc}"
        ),
        "Programathor (TI)": (
            f"https://programathor.com.br/jobs?search={cargo_enc}"
        ),
        "Glassdoor Brasil": (
            f"https://www.glassdoor.com.br/Vaga/brasil-{cargo_slug}-vagas-SRCH_IL.0,6_IN36.htm"
        ),
        "Empregos.com.br": (
            f"https://www.empregos.com.br/vagas/?keywords={cargo_enc}"
        ),
    }


def render():
    """Renderiza o módulo de Atalhos de Busca."""
    st.title("Atalhos de Busca")
    st.caption(
        "Abre as maiores plataformas de vagas com busca pré-preenchida. "
        "Faça login manualmente em cada site para ver os resultados."
    )

    st.info(
        "📌 **Perfil otimizado:** CTO | Head de TI | CIO | Diretor de TI — "
        "setores: Saúde, Fintechs, Empresas de grande porte. "
        "Localizações: Campinas, São Paulo, Remoto."
    )

    # Cargo e localização
    col_cargo, col_local = st.columns(2)
    with col_cargo:
        cargo_select = st.selectbox(
            "Cargo para busca",
            options=CARGOS,
            index=0,
            help="Cargos priorizados conforme seu currículo",
        )
        cargo_aux = st.text_input(
            "Ou digite outro cargo",
            placeholder="Ex: Arquiteto de Soluções, Engenheiro de Dados...",
            key="atalhos_cargo_aux",
        )
    with col_local:
        local = st.selectbox(
            "Localização",
            options=LOCALIZACOES,
            index=0,
        )

    cargo = cargo_aux.strip() if cargo_aux and cargo_aux.strip() else cargo_select
    links = _montar_links(cargo, local)

    st.subheader("Top 10 plataformas de vagas no Brasil")
    st.caption("Clique para abrir a busca em nova aba (faça login no site):")

    prioridade = [
        ("LinkedIn Jobs", "Maior rede profissional"),
        ("Indeed Brasil", "Agregador global"),
        ("Catho", "Tradicional no Brasil"),
        ("Vagas.com", "Grande base de vagas"),
        ("InfoJobs", "Presente em todo Brasil"),
        ("Trabalha Brasil", "Foco em CLT"),
        ("GeekHunter (TI)", "Especializado em tech"),
        ("Programathor (TI)", "Desenvolvedores e TI"),
        ("Glassdoor Brasil", "Com avaliações de empresa"),
        ("Empregos.com.br", "Portal consolidado"),
    ]

    cols = st.columns(2)
    for idx, (nome, desc) in enumerate(prioridade):
        url = links.get(nome, "")
        if url:
            with cols[idx % 2]:
                st.link_button(
                    f"🔗 {nome} — {cargo}",
                    url,
                    use_container_width=True,
                    help=desc,
                )

    st.divider()
    st.subheader("🏥 Plataformas hospitalares")
    st.caption("Carreiras em hospitais e redes de saúde (busca manual no site):")

    plataformas_hospitais = [
        (
            "Albert Einstein",
            "https://career8.successfactors.com/career?company=C0001240283P&career_ns=job_listing_summary&navBarLevel=JOB_SEARCH",
            "São Paulo — Hospital Israelita Albert Einstein",
        ),
    ]

    cols_h = st.columns(2)
    for idx, (nome, url, desc) in enumerate(plataformas_hospitais):
        with cols_h[idx % 2]:
            st.link_button(
                f"🏥 {nome}",
                url,
                use_container_width=True,
                help=desc,
            )
