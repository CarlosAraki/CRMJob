"""
Módulo de Busca Ativa - Scraping e agregador de vagas.
Busca em portais abertos (GitHub, Programathor, BHjobs RSS) pelos cargos alvo.
"""

import re
import streamlit as st
import requests
from bs4 import BeautifulSoup

from database import inserir_vaga, listar_vagas
from config import PERFIL_PADRAO

CARGOS_ALVO = PERFIL_PADRAO["cargos_alvo"]
USER_AGENT = "CRMJobBot/1.0 (Personal Job Search CRM)"


def _normalizar_termo(termo: str) -> str:
    """Remove acentos e normaliza para busca."""
    return termo.lower().strip()


def _cargo_compativel(titulo: str, cargo: str) -> bool:
    """Verifica se o título da vaga contém o cargo alvo (case insensitive, flexível)."""
    t = _normalizar_termo(titulo)
    c = _normalizar_termo(cargo)
    # Match exato ou como palavra (evita "CT"匹配 "CTO")
    return c in t or re.search(rf"\b{re.escape(c)}\b", t, re.IGNORECASE) is not None


# Termos adicionais para ampliar a busca (além dos cargos alvo)
TERMOS_BUSCA_EXTRA = ["líder", "lider", "senior", "sênior", "tech lead", "director", "diretor", "architect", "arquiteto"]


def _titulo_relevante(titulo: str) -> bool:
    """Verifica se o título é relevante para os cargos alvo."""
    t = _normalizar_termo(titulo)
    todos_termos = CARGOS_ALVO + TERMOS_BUSCA_EXTRA
    return any(_cargo_compativel(titulo, c) for c in CARGOS_ALVO) or any(
        term in t for term in TERMOS_BUSCA_EXTRA
    )


def buscar_github_vagas() -> list[dict]:
    """Busca vagas no repositório backend-br/vagas via GitHub API."""
    vagas = []
    try:
        url = "https://api.github.com/repos/backend-br/vagas/issues"
        resp = requests.get(
            url,
            params={"state": "open", "per_page": 50, "sort": "updated"},
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT},
            timeout=15,
        )
        if resp.status_code != 200:
            return [{"_erro": f"GitHub API retornou {resp.status_code}"}]
        items = resp.json()
        for item in items:
            titulo = item.get("title", "")
            if not _titulo_relevante(titulo):
                continue
            html_url = item.get("html_url", "")
            body = (item.get("body") or "")[:2000]
            vagas.append({
                "fonte": "GitHub (backend-br/vagas)",
                "titulo": titulo,
                "empresa": _extrair_empresa_titulo(titulo),
                "cargo": titulo,
                "link": html_url,
                "descricao": body,
                "data_limite": None,
            })
        return vagas[:40]
    except Exception as e:
        return [{"_erro": str(e)}]


def _extrair_empresa_titulo(titulo: str) -> str:
    """Tenta extrair o nome da empresa do título (ex: '[...] Cargo - Empresa')."""
    # Formato comum: [Local] Cargo - Empresa ou [Remoto] Cargo - Empresa
    parts = titulo.split(" - ")
    if len(parts) >= 2:
        return parts[-1].strip()
    return "Empresa não informada"


def buscar_programathor() -> list[dict]:
    """Busca vagas no Programathor (scraping simplificado)."""
    vagas = []
    try:
        urls = [
            "https://programathor.com.br/jobs",
            "https://programathor.com.br/jobs-city/remoto",
            "https://programathor.com.br/jobs-city/campinas",
            "https://programathor.com.br/jobs-city/sao-paulo",
        ]
        for url in urls:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # Cards de vaga: links para /jobs/ID-titulo
            for a in soup.select('a[href*="/jobs/"]'):
                href = a.get("href", "")
                if "/jobs/" not in href or href.endswith("/jobs"):
                    continue
                full_url = f"https://programathor.com.br{href}" if href.startswith("/") else href
                texto = a.get_text(strip=True)
                if len(texto) < 5:
                    continue
                # Verifica se algum cargo alvo está no texto
                if not any(_cargo_compativel(texto, c) for c in CARGOS_ALVO):
                    # Também inclui "Head", "Gerente", "CTO" em variações
                    termos_extras = ["head", "gerente", "cto", "líder", "leader"]
                    if not any(t in _normalizar_termo(texto) for t in termos_extras):
                        continue
                # Extrai empresa (geralmente primeira linha) e cargo
                linhas = [l.strip() for l in texto.split("\n") if l.strip()]
                cargo = linhas[0] if linhas else texto[:80]
                empresa = linhas[1] if len(linhas) > 1 else "Programathor"
                vagas.append({
                    "fonte": "Programathor",
                    "titulo": cargo,
                    "empresa": empresa,
                    "cargo": cargo,
                    "link": full_url,
                    "descricao": f"Vaga encontrada no Programathor. Acesse o link para detalhes.",
                    "data_limite": None,
                })
        # Deduplica
        seen = set()
        unicos = []
        for v in vagas:
            if v["link"] not in seen:
                seen.add(v["link"])
                unicos.append(v)
        return unicos[:30]  # Limita resultado
    except Exception as e:
        return [{"_erro": str(e)}] if not vagas else vagas


def buscar_bhjobs_rss() -> list[dict]:
    """Busca vagas no BHjobs via RSS (categoria TI)."""
    vagas = []
    try:
        url = "https://www.bhjobs.com.br/rss/informatica-ti-internet-telecomunicacoes/"
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        ns = {"dc": "http://purl.org/dc/elements/1.1/", "content": "http://purl.org/rss/1.0/modules/content/"}
        items = root.findall(".//item") or root.findall(".//{http://purl.org/rss/1.0/}item")
        if not items:
            items = root.findall(".//item")
        for item in items:
            title_el = item.find("title") or item.find("{http://purl.org/rss/1.0/}title")
            link_el = item.find("link") or item.find("{http://purl.org/rss/1.0/}link")
            desc_el = item.find("description") or item.find("{http://purl.org/rss/1.0/}description")
            titulo = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            desc = (desc_el.text or "").strip() if desc_el is not None else ""
            if not titulo or not link:
                continue
            if not any(_cargo_compativel(titulo, c) for c in CARGOS_ALVO):
                termos = ["cto", "head", "gerente", "diretor", "gestor", "líder"]
                if not any(t in _normalizar_termo(titulo) for t in termos):
                    continue
            vagas.append({
                "fonte": "BHjobs (RSS TI)",
                "titulo": titulo,
                "empresa": _extrair_empresa_titulo(titulo),
                "cargo": titulo,
                "link": link,
                "descricao": desc[:2000] if desc else "Acesse o link para detalhes.",
                "data_limite": None,
            })
        return vagas[:25]
    except Exception as e:
        return []


def buscar_todas() -> tuple[list[dict], list[str]]:
    """
    Executa busca em todas as fontes.
    Retorna (lista de vagas, lista de erros).
    """
    todas = []
    erros = []
    # GitHub
    gh = buscar_github_vagas()
    if gh and isinstance(gh[0].get("_erro"), str):
        erros.append(f"GitHub: {gh[0]['_erro']}")
    else:
        todas.extend(gh)
    # Programathor
    pt = buscar_programathor()
    if pt and isinstance(pt[0].get("_erro"), str):
        erros.append(f"Programathor: {pt[0]['_erro']}")
    else:
        todas.extend([v for v in pt if "_erro" not in v])
    # BHjobs
    bh = buscar_bhjobs_rss()
    todas.extend(bh)
    return todas, erros


def _vaga_ja_no_crm(link: str) -> bool:
    """Verifica se já existe uma vaga com esse link no CRM."""
    vagas = listar_vagas()
    return any((v.get("link") or "").strip() == link.strip() for v in vagas)


def render():
    """Renderiza o módulo de Busca Ativa."""
    st.title("Busca Ativa de Vagas")
    st.caption(
        f"Busca automática nos cargos alvo: {', '.join(CARGOS_ALVO)}. "
        "Clique em 'Adicionar ao CRM' para incluir no funil."
    )

    if st.button("🔍 Buscar vagas agora", type="primary", key="btn_buscar_vagas"):
        with st.spinner("Buscando em GitHub, Programathor e BHjobs..."):
            vagas, erros = buscar_todas()
            st.session_state["busca_resultados"] = vagas
            st.session_state["busca_erros"] = erros
        st.rerun()

    erros = st.session_state.get("busca_erros", [])
    if erros:
        for e in erros:
            st.warning(e)

    vagas = st.session_state.get("busca_resultados", [])

    if not vagas:
        st.info(
            "Clique em **Buscar vagas agora** para procurar oportunidades nos portais "
            "(GitHub backend-br/vagas, Programathor, BHjobs)."
        )
        return

    st.success(f"Encontradas **{len(vagas)}** vaga(s)")

    for i, v in enumerate(vagas):
        if "_erro" in v:
            continue
        ja_no_crm = _vaga_ja_no_crm(v["link"])
        with st.container():
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f"**{v['cargo']}**")
                st.caption(f"{v['empresa']} | {v['fonte']}")
                if v["link"]:
                    st.markdown(f"[🔗 Ver vaga]({v['link']})")
            with col_btn:
                if ja_no_crm:
                    st.caption("✓ Já no CRM")
                elif st.button("➕ Adicionar ao CRM", key=f"add_{i}"):
                    try:
                        inserir_vaga(
                            link=v["link"],
                            empresa=v["empresa"],
                            cargo=v["cargo"],
                            data_limite=None,
                            descricao=v.get("descricao", "") or "",
                            plataforma=v.get("fonte"),
                        )
                        st.success("Adicionada!")
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
            st.divider()
