"""
Módulo de banco de dados SQLite para o CRM de Busca de Emprego.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from config import STATUS_VAGAS

# Permite DB_PATH via env para Docker (volume persistente)
_DEFAULT_DB = Path(__file__).parent / "crm_job.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(_DEFAULT_DB)))


def get_connection():
    """Retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Retorna dicionários em vez de tuplas
    return conn


def init_db():
    """Inicializa o banco de dados criando as tabelas necessárias."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT,
            empresa TEXT NOT NULL,
            cargo TEXT NOT NULL,
            data_limite DATE,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'Mapeada',
            curriculo_adaptado TEXT,
            plataforma TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migração: adiciona coluna plataforma se não existir
    cursor.execute("PRAGMA table_info(vagas)")
    colunas = [row[1] for row in cursor.fetchall()]
    if "plataforma" not in colunas:
        cursor.execute("ALTER TABLE vagas ADD COLUMN plataforma TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            nota TEXT,
            data_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vaga_id) REFERENCES vagas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Currículos (versionamento de PDFs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curriculums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            versao TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Documentos vinculados às vagas (currículo enviado + anexos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vaga_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            curriculum_id INTEGER,
            caminho_arquivo TEXT,
            nome TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vaga_id) REFERENCES vagas(id),
            FOREIGN KEY (curriculum_id) REFERENCES curriculums(id)
        )
    """)

    conn.commit()
    conn.close()


def listar_vagas(
    filtro_status: Optional[str] = None,
    filtro_empresa: Optional[str] = None,
    filtro_plataforma: Optional[str] = None,
    ordenar_por: str = "prioridade_funil",
    ordem: str = "asc",
    excluir_rejeitadas: bool = True,
) -> list[dict]:
    """Lista vagas com filtros e ordenação."""
    conn = get_connection()
    cursor = conn.cursor()

    where_parts = []
    params = []

    if filtro_status:
        where_parts.append("status = ?")
        params.append(filtro_status)
    elif excluir_rejeitadas:
        where_parts.append("status != 'Rejeitada'")
    if filtro_empresa and filtro_empresa.strip():
        where_parts.append("LOWER(empresa) LIKE ?")
        params.append(f"%{filtro_empresa.strip().lower()}%")
    if filtro_plataforma and filtro_plataforma.strip():
        where_parts.append("LOWER(plataforma) LIKE ?")
        params.append(f"%{filtro_plataforma.strip().lower()}%")

    where_sql = " AND ".join(where_parts) if where_parts else "1=1"

    # Prioridade: Proposta, Entrevista, Currículo Enviado, Em Adaptação, Mapeada, Rejeitada
    if ordenar_por == "prioridade_funil":
        order_sql = (
            "CASE status "
            "WHEN 'Proposta' THEN 1 WHEN 'Entrevista' THEN 2 WHEN 'Currículo Enviado' THEN 3 "
            "WHEN 'Em Adaptação' THEN 4 WHEN 'Mapeada' THEN 5 WHEN 'Rejeitada' THEN 6 "
            "ELSE 7 END ASC, COALESCE(data_limite, '9999-99-99') ASC"
        )
    else:
        order_col = {
            "data_limite": "data_limite",
            "empresa": "empresa",
            "criado_em": "criado_em",
        }.get(ordenar_por, "criado_em")
        dir_sql = "ASC" if ordem.lower() == "asc" else "DESC"
        if order_col == "data_limite":
            order_sql = f"COALESCE({order_col}, '9999-99-99') {dir_sql}"
        else:
            order_sql = f"{order_col} {dir_sql}"

    sql = f"SELECT * FROM vagas WHERE {where_sql} ORDER BY {order_sql}"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def obter_vaga(vaga_id: int) -> Optional[dict]:
    """Retorna uma vaga pelo ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vagas WHERE id = ?", (vaga_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def inserir_vaga(
    link: str,
    empresa: str,
    cargo: str,
    data_limite: Optional[str],
    descricao: str,
    plataforma: Optional[str] = None,
) -> int:
    """Insere uma nova vaga e retorna o ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vagas (link, empresa, cargo, data_limite, descricao, plataforma)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (link or "", empresa, cargo, data_limite, descricao or "", plataforma or ""),
    )
    vaga_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return vaga_id


def atualizar_vaga(
    vaga_id: int,
    link: Optional[str] = None,
    empresa: Optional[str] = None,
    cargo: Optional[str] = None,
    data_limite: Optional[str] = None,
    descricao: Optional[str] = None,
    status: Optional[str] = None,
    curriculo_adaptado: Optional[str] = None,
    plataforma: Optional[str] = None,
) -> bool:
    """Atualiza uma vaga existente."""
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if link is not None:
        updates.append("link = ?")
        params.append(link)
    if empresa is not None:
        updates.append("empresa = ?")
        params.append(empresa)
    if cargo is not None:
        updates.append("cargo = ?")
        params.append(cargo)
    if data_limite is not None:
        updates.append("data_limite = ?")
        params.append(data_limite)
    if descricao is not None:
        updates.append("descricao = ?")
        params.append(descricao)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if curriculo_adaptado is not None:
        updates.append("curriculo_adaptado = ?")
        params.append(curriculo_adaptado)
    if plataforma is not None:
        updates.append("plataforma = ?")
        params.append(plataforma)

    if not updates:
        conn.close()
        return False

    updates.append("atualizado_em = ?")
    params.append(datetime.now().isoformat())
    params.append(vaga_id)

    cursor.execute(
        f"UPDATE vagas SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def excluir_vaga(vaga_id: int) -> bool:
    """Exclui uma vaga."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vaga_documentos WHERE vaga_id = ?", (vaga_id,))
    cursor.execute("DELETE FROM interacoes WHERE vaga_id = ?", (vaga_id,))
    cursor.execute("DELETE FROM vagas WHERE id = ?", (vaga_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def listar_vagas_para_alerta() -> list[dict]:
    """
    Retorna vagas para alerta Telegram:
    - Status Mapeada ou Em Adaptação (sempre)
    - OU qualquer outro status (exceto Rejeitada) que tenha data_limite preenchida
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM vagas
        WHERE status IN ('Mapeada', 'Em Adaptação')
           OR (status != 'Rejeitada' AND data_limite IS NOT NULL)
        ORDER BY COALESCE(data_limite, '9999-99-99') ASC, criado_em ASC
        """,
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def obter_config(chave: str) -> Optional[str]:
    """Obtém um valor de configuração."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
    row = cursor.fetchone()
    conn.close()
    return row["valor"] if row else None


# --- Currículos ---
def listar_curriculums() -> list[dict]:
    """Lista todos os currículos versionados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM curriculums ORDER BY criado_em DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def inserir_curriculum(nome: str, versao: str, caminho_arquivo: str) -> int:
    """Insere novo currículo versionado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO curriculums (nome, versao, caminho_arquivo) VALUES (?, ?, ?)",
        (nome, versao, caminho_arquivo),
    )
    cid = cursor.lastrowid
    conn.commit()
    conn.close()
    return cid


def obter_curriculum(curriculum_id: int) -> Optional[dict]:
    """Retorna currículo por ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM curriculums WHERE id = ?", (curriculum_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def excluir_curriculum(curriculum_id: int) -> bool:
    """Exclui currículo (desvincula de vagas antes)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE vaga_documentos SET curriculum_id = NULL WHERE curriculum_id = ?", (curriculum_id,))
    cursor.execute("DELETE FROM curriculums WHERE id = ?", (curriculum_id,))
    n = cursor.rowcount
    conn.commit()
    conn.close()
    return n > 0


# --- Documentos vinculados às vagas ---
TIPOS_DOCUMENTO = ["curriculum", "resposta_vaga", "carta_apresentacao", "carta_recomendacao"]


def listar_documentos_vaga(vaga_id: int) -> list[dict]:
    """Lista documentos vinculados a uma vaga."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.*, c.nome as curriculum_nome, c.versao as curriculum_versao
        FROM vaga_documentos d
        LEFT JOIN curriculums c ON d.curriculum_id = c.id
        WHERE d.vaga_id = ?
        ORDER BY d.tipo, d.criado_em DESC
        """,
        (vaga_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def vincular_documento_vaga(
    vaga_id: int,
    tipo: str,
    nome: str,
    curriculum_id: Optional[int] = None,
    caminho_arquivo: Optional[str] = None,
) -> int:
    """Vincula documento a uma vaga. Retorna ID do documento."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vaga_documentos (vaga_id, tipo, curriculum_id, caminho_arquivo, nome)
        VALUES (?, ?, ?, ?, ?)
        """,
        (vaga_id, tipo, curriculum_id, caminho_arquivo, nome),
    )
    did = cursor.lastrowid
    conn.commit()
    conn.close()
    return did


def excluir_documento_vaga(documento_id: int) -> bool:
    """Exclui documento vinculado à vaga."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vaga_documentos WHERE id = ?", (documento_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def salvar_config(chave: str, valor: str) -> None:
    """Salva ou atualiza um valor de configuração."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO configuracoes (chave, valor, atualizado_em)
        VALUES (?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor = ?, atualizado_em = ?
        """,
        (chave, valor, datetime.now().isoformat(), valor, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
