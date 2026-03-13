#!/usr/bin/env python3
"""
Script para rodar alertas do Telegram em modo headless.
Use com cron para verificação periódica (ex: a cada 6h):
  0 */6 * * * cd /caminho/CRMJOB && python run_alertas.py
"""

import os
import sys

# Garante que o diretório do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.alertas_telegram import verificar_e_enviar_alertas


def main():
    enviados, erros = verificar_e_enviar_alertas()
    if enviados > 0:
        print(f"✅ {enviados} alerta(s) enviado(s)")
    if erros:
        for e in erros:
            print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
