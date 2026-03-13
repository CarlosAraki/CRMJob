# CRM Pessoal de Busca de Emprego

Sistema on-premise para gestão de vagas, geração de prompts para IA e tracking de candidaturas.

## Stack

- **Interface:** Streamlit
- **Banco:** SQLite
- **Notificações:** python-telegram-bot (em breve)
- **Scraping:** BeautifulSoup / APIs gratuitas (em breve)

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Executar

**Local:**
```bash
streamlit run app.py
```

**Docker (servidor 24/7 na porta 9991):**
```bash
docker compose up -d --build
# Acesse: http://localhost:9991
# Ou http://IP_DO_SERVIDOR:9991
```

Para parar: `docker compose down`

**Alertas automáticos (opcional):** Para rodar alertas via cron no host, monte o volume e use:
```bash
# Exemplo: a cada 6 horas
0 */6 * * * docker exec crm-busca-emprego python run_alertas.py
```

## Módulos Implementados

1. **Funil de Vagas (CRM)** – Kanban/Tabela com status: Mapeada, Em Adaptação, Currículo Enviado, Entrevista, Proposta, Rejeitada
2. **Gerador de Prompts** – Gera prompts para copiar em IAs web gratuitas e salva o resultado adaptado
3. **Alertas Telegram** – Configura Bot Token e Chat ID; envia avisos quando vagas mapeadas há +2 dias ainda não tiveram currículo enviado

4. **Busca Ativa** – Busca vagas em GitHub (backend-br/vagas), Programathor e BHjobs (RSS TI); botão "Adicionar ao CRM" para incluir no funil

5. **Atalhos de Busca** – Links diretos para as 10 maiores plataformas com busca pré-preenchida conforme perfil

6. **Importar por URL** – Suas vagas de interesse (Agibank, Santander, Unilever, KPMG, Meta, CPQD, Unimed, Hospital Care, LATAM, Azul, John Deere, DHL, Ambev, Rumo, Boticário). Reconhece Greenhouse, Gupy, Workday, Recruitee e outras plataformas


