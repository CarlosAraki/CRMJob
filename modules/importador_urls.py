"""
Módulo Importador por URL - Vagas de interesse em plataformas variadas.
Reconhece Greenhouse, Gupy, Workday, Recruitee, SuccessFactors, etc.
Crawler automático para extrair descrição e data limite das páginas.
"""

import re
from datetime import datetime
from typing import Optional

import requests
import streamlit as st
from bs4 import BeautifulSoup

from database import inserir_vaga, listar_vagas

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Mapeamento: padrão na URL -> (plataforma, empresa)
# Ordem importa: padrões mais específicos primeiro
URL_MAP = [
    (r"greenhouse\.io/([^/]+)", "Greenhouse", lambda m: m.group(1).replace("-", " ").title()),
    (r"workdayjobs\.com[^/]*/([^/]+)", "Workday", lambda m: m.group(1).replace("-", " ").title()),
    (r"careers\.unilever\.com", "Unilever Careers", lambda _: "Unilever"),
    (r"inhire\.app[^/]*/[^/]+/[^/]+/([^/?]+)", "InHire", lambda m: m.group(1).replace("-", " ").title()),
    (r"recrut\.ai[^/]*/vagas/job/([^/?]+)", "Recrut.AI", lambda _: "Meta"),
    (r"recruitee\.com/o/([^/?]+)", "Recruitee", lambda m: m.group(1).split("-")[0].upper() if m.group(1) else "Empresa"),
    (r"successfactors\.com[^?]*company=([^&]+)", "SuccessFactors", lambda m: {"lan": "LATAM"}.get(m.group(1).lower(), m.group(1).upper())),
    (r"careers\.deere\.com", "John Deere", lambda _: "John Deere"),
    (r"careers\.dhl\.com", "DHL", lambda _: "DHL"),
    # Gupy: extrair empresa do subdomínio (empresa.gupy.io)
    (r"([a-z0-9]+)\.gupy\.io", "Gupy", lambda m: _gupy_empresa(m.group(1))),
    (r"ambevtech\.gupy\.io", "Gupy", lambda _: "Ambev Tech"),
    (r"rumolog\.gupy\.io", "Gupy", lambda _: "Rumo"),
    (r"grupoboticario\.gupy\.io", "Gupy", lambda _: "Grupo Boticário"),
    # Fallback por domínio
    (r"wd\d+\.myworkdayjobs\.com[^/]*/[^/]+", "Workday", lambda _: "Empresa"),
]

GUPY_EMPRESAS = {
    "unimedcampinas": "Unimed Campinas",
    "hospitalcare": "Hospital Care",
    "voeazul": "Azul",
    "ambevtech": "Ambev Tech",
    "rumolog": "Rumo",
    "grupoboticario": "Grupo Boticário",
}


def _gupy_empresa(subdomain: str) -> str:
    return GUPY_EMPRESAS.get(subdomain.lower(), subdomain.replace("-", " ").title())


def _parse_url(url: str) -> tuple[str, str, str]:
    """
    Analisa URL e retorna (plataforma, empresa, cargo_sugerido).
    cargo_sugerido pode vir do path quando possível.
    """
    url_limpa = url.strip()
    if not url_limpa or not url_limpa.startswith(("http://", "https://")):
        return ("", "", "")

    plataforma = "Outros"
    empresa = "Empresa"
    cargo = ""

    for pattern, plat, emp_fn in URL_MAP:
        m = re.search(pattern, url_limpa, re.IGNORECASE)
        if m:
            plataforma = plat
            try:
                empresa = emp_fn(m)
            except Exception:
                empresa = "Empresa"
            break

    # Tentar extrair cargo do path (ex: /gerente-executivo-de-solucoes...)
    path_match = re.search(r"/([a-z0-9-]+(?:-[a-z0-9-]+)*)(?:\?|$)", url_limpa.split("/", 3)[-1] if "/" in url_limpa else "")
    if path_match:
        path_part = path_match.group(1)
        if len(path_part) > 5 and "job" not in path_part.lower():
            cargo = path_part.replace("-", " ").title()

    return (plataforma, empresa, cargo)


# Regex para capturar datas em textos de vagas (BR: DD/MM/YYYY, ISO: YYYY-MM-DD)
REGEX_DATAS = [
    (r"(?:até|prazo|limite|data\s+limite|inscrições\s+até|candidatar\s+até|enviar\s+até)[:\s]*(\d{1,2})/(\d{1,2})/(\d{4})", (2, 1, 0)),  # DD/MM/YYYY
    (r"(?:até|prazo|limite)[:\s]*(\d{1,2})/(\d{1,2})", (0, 1)),  # DD/MM (ano atual)
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", (2, 1, 0)),  # DD/MM/YYYY genérico
    (r"(\d{4})-(\d{2})-(\d{2})", (0, 1, 2)),  # ISO YYYY-MM-DD
    (r"(\d{1,2})-(\d{1,2})-(\d{4})", (2, 1, 0)),  # DD-MM-YYYY
]


def _normalizar_data(grupos: tuple, ordem: tuple) -> Optional[str]:
    """Converte grupos do regex em YYYY-MM-DD. ordem = (idx_ano, idx_mes, idx_dia)."""
    try:
        if len(ordem) == 3:
            ano = int(grupos[ordem[0]])
            mes = int(grupos[ordem[1]])
            dia = int(grupos[ordem[2]])
        else:
            ano = datetime.now().year
            mes = int(grupos[ordem[1]])
            dia = int(grupos[ordem[0]])
        if 1 <= mes <= 12 and 1 <= dia <= 31:
            return f"{ano:04d}-{mes:02d}-{dia:02d}"
    except (ValueError, IndexError):
        pass
    return None


def _extrair_data_limite(texto: str) -> Optional[str]:
    """Busca data limite no texto usando regex."""
    if not texto or len(texto) < 10:
        return None
    texto_lower = texto.lower()
    for pattern, ordem in REGEX_DATAS:
        m = re.search(pattern, texto_lower, re.IGNORECASE)
        if m:
            data = _normalizar_data(m.groups(), ordem)
            if data:
                return data
    return None


def _crawl_vaga(url: str) -> dict:
    """
    Faz crawl da página da vaga e extrai descrição, data limite e cargo.
    Retorna {'descricao': str, 'data_limite': str|None, 'cargo': str}.
    """
    resultado = {"descricao": "", "data_limite": None, "cargo": ""}
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts e styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        texto_completo = soup.get_text(separator=" ", strip=True)

        # 1. Descrição: meta og:description ou meta description
        for tag, attrs in [
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "description"}),
        ]:
            meta = soup.find(tag, attrs)
            if meta and meta.get("content"):
                resultado["descricao"] = meta["content"].strip()[:3000]
                break

        # 2. Se não achou meta, busca em containers comuns de job description
        if not resultado["descricao"]:
            candidatos = [
                soup.find(attrs={"data-qa": "job-description"}),
                soup.find(attrs={"id": "job-description"}),
                soup.find(class_=lambda c: c and "job-description" in str(c).lower()),
                soup.find(class_=lambda c: c and "jobdescription" in str(c).lower()),
                soup.find(class_=lambda c: c and "descricao" in str(c).lower()),
            ]
            for el in candidatos:
                if el:
                    txt = el.get_text(separator="\n", strip=True)
                    if len(txt) > 100:
                        resultado["descricao"] = txt[:3000]
                        break

        # 3. Fallback: main, article ou div com muito texto
        if not resultado["descricao"]:
            for tag in ["main", "article", "[role='main']"]:
                el = soup.select_one(tag) if tag.startswith("[") else soup.find(tag)
                if el:
                    txt = el.get_text(separator="\n", strip=True)
                    if len(txt) > 200:
                        resultado["descricao"] = txt[:3000]
                        break

        # 4. Fallback final: primeiros 2000 chars do body
        if not resultado["descricao"] and len(texto_completo) > 100:
            resultado["descricao"] = texto_completo[:2000]

        # 5. Data limite via regex no texto
        resultado["data_limite"] = _extrair_data_limite(resultado["descricao"] or texto_completo)

        # 6. Cargo: og:title ou h1
        for el in [soup.find("meta", {"property": "og:title"}), soup.find("h1")]:
            if el:
                titulo = el.get("content") if el.name == "meta" else el.get_text(strip=True)
                if titulo and len(titulo) > 2 and len(titulo) < 150:
                    resultado["cargo"] = titulo.strip()
                    break

    except Exception:
        pass
    return resultado


# Vagas de interesse pré-carregadas (do perfil do usuário)
VAGAS_INTERESSE = [
    ("https://job-boards.greenhouse.io/agibank/jobs/5115376008?gh_src=LinkedIn", "Agibank", "IT Architecture Manager", "Greenhouse", "Campinas/SP"),
    ("https://santander.wd3.myworkdayjobs.com/pt-BR/SantanderCareers/job/CAMPINAS/SSD-Brasil---IT-Leader--Data-Center-_Req1506712", "Santander", "IT Leader - Data Center", "Workday", "Campinas"),
    ("https://careers.unilever.com/en/job/-/-/34155/92655028112", "Unilever", "Coordenador de Tecnologia e Inovação Packing", "Unilever Careers", "Vinhedo/SP"),
    ("https://kpmg.inhire.app/vagas/560350ce-3465-43fd-b6f3-2f6e64a65fa6/gerente-de-transformacao-ia-latam", "KPMG", "Gerente de Transformação IA Latam", "InHire", "Remoto"),
    ("https://meta.jobs.recrut.ai/vagas/job/YBXY4J?source=linkedin", "Meta", "Tech Lead I", "Recrut.AI", "Remoto"),
    ("https://cpqd.recruitee.com/o/gerente-executivo-de-solucoes-foco-em-ia-e-ciencia-de-dados", "CPQD", "Gerente Executivo - IA e Ciência de Dados", "Recruitee", "Campinas (Híbrido)"),
    ("https://unimedcampinas.gupy.io/job/eyJqb2JJZCI6MTA3MTIyMzQsInNvdXJjZSI6ImxpbmtlZGluIn0=", "Unimed Campinas", "Coordenador(a) de Processos", "Gupy", "Campinas"),
    ("https://hospitalcare.gupy.io/job/eyJqb2JJZCI6MTA4MjUzMjIsInNvdXJjZSI6ImxpbmtlZGluIn0=", "Hospital Care", "Coordenador de TI", "Gupy", "Rede Hospitalar"),
    ("https://career8.successfactors.com/sfcareer/jobreqcareer?jobId=538610&company=lan", "LATAM", "Digital Team Lead", "SuccessFactors", "Santiago/Chile"),
    ("https://voeazul.gupy.io/job/eyJqb2JJZCI6MTA5NTI0NjEsInNvdXJjZSI6ImxpbmtlZGluIn0=", "Azul", "Supervisor Infraestrutura", "Gupy", "Campinas"),
    ("https://careers.unilever.com/en/job/-/-/34155/92608245408", "Unilever", "Coordenador de Tecnologia e Inovação Hair", "Unilever Careers", "Vinhedo/SP"),
    ("https://careers.deere.com/careers/job/137479375222", "John Deere", "Gerente de Data Science", "John Deere", "Indaiatuba/SP"),
    ("https://careers.dhl.com/global/en/job/DPDHGLOBALBR38599ENGLOBALEXTERNALLUMESSELATAM/Gerência-de-TI", "DHL", "Gerência de TI", "DHL", "Campinas"),
    ("https://ambevtech.gupy.io/jobs/10713674?jobBoardSource=linkedin", "Ambev Tech", "Gerente Tech I", "Gupy", "Campinas/Jaguariúna"),
    ("https://rumolog.gupy.io/job/eyJqb2JJZCI6MTA4MTcwMzUsInNvdXJjZSI6ImxpbmtlZGluIn0=", "Rumo", "Coordenador(a) Infraestrutura TI", "Gupy", "Indaiatuba/SP"),
    ("https://grupoboticario.gupy.io/jobs/10777868?jobBoardSource=linkedin", "Grupo Boticário", "Tech Manager I (B2B e B2P)", "Gupy", "Curitiba/Remoto"),
]


def _vaga_ja_no_crm(link: str) -> bool:
    vagas = listar_vagas()
    return any((v.get("link") or "").strip() == link.strip() for v in vagas)


def render():
    """Renderiza o módulo Importador por URL."""
    if st.button("← Voltar ao CRM"):
        st.session_state["navegar_para"] = "crm"
        st.rerun()

    st.title("Importar Vagas por URL")
    st.caption(
        "Adicione vagas ao CRM a partir de links. O sistema reconhece automaticamente "
        "plataformas como Greenhouse, Gupy, Workday, Recruitee, SuccessFactors e outras."
    )

    st.divider()
    st.subheader("Importar URL personalizada")
    st.caption("Cole um ou mais links de vagas (um por linha) para importar.")

    urls_texto = st.text_area(
        "URLs das vagas",
        placeholder="https://empresa.gupy.io/job/...\nhttps://careers.empresa.com/job/...",
        height=120,
        key="import_urls_text",
    )

    if st.button("Analisar e adicionar ao CRM", key="btn_analisar_urls"):
        linhas = [l.strip() for l in urls_texto.split("\n") if l.strip()]
        urls_validas = [u for u in linhas if u.startswith(("http://", "https://"))]

        if not urls_validas:
            st.warning("Nenhuma URL válida encontrada.")
        else:
            adicionadas = 0
            with st.spinner("Analisando URLs e extraindo dados das páginas..."):
                for url in urls_validas:
                    if _vaga_ja_no_crm(url):
                        continue
                    plat, emp, cargo_sug = _parse_url(url)
                    crawl = _crawl_vaga(url)
                    cargo_final = (crawl.get("cargo") or cargo_sug or "Vaga").strip()
                    descricao = (crawl.get("descricao") or f"Importada de {plat}.").strip()
                    data_limite = crawl.get("data_limite")
                    inserir_vaga(
                        link=url,
                        empresa=emp,
                        cargo=cargo_final,
                        data_limite=data_limite,
                        descricao=descricao[:3000] if descricao else f"Importada de {plat}.",
                        plataforma=plat,
                    )
                    adicionadas += 1
            if adicionadas > 0:
                st.success(f"✅ {adicionadas} vaga(s) adicionada(s) ao CRM!")
                st.rerun()
            else:
                st.info("Todas as vagas já estavam no CRM.")

    st.divider()
    st.subheader("Suas vagas de interesse")
    st.caption("Vagas nas empresas e plataformas que você indicou. Clique para adicionar ao CRM.")

    for i, (url, empresa, cargo, plataforma, local) in enumerate(VAGAS_INTERESSE):
        ja_no_crm = _vaga_ja_no_crm(url)
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{cargo}** — *{empresa}*")
                st.caption(f"📍 {local}  |  {plataforma}")
                st.markdown(f"[🔗 Abrir vaga]({url})")
            with col2:
                if ja_no_crm:
                    st.success("✓ No CRM")
                elif st.button("➕ CRM", key=f"vi_{i}"):
                    with st.spinner("Extraindo dados da página..."):
                        crawl = _crawl_vaga(url)
                    cargo_f = (crawl.get("cargo") or cargo).strip()
                    desc = (crawl.get("descricao") or f"Vaga em {plataforma}. Local: {local}.").strip()
                    data_lim = crawl.get("data_limite")
                    inserir_vaga(
                        link=url,
                        empresa=empresa,
                        cargo=cargo_f,
                        data_limite=data_lim,
                        descricao=desc[:3000] if desc else f"Vaga em {plataforma}. Local: {local}.",
                        plataforma=plataforma,
                    )
                    st.success("Adicionada!")
                    st.rerun()
            st.divider()

