# -*- coding: utf-8 -*-
"""Integração de departamentos: Contabit /lotacao → departamentos_api.csv → Hevi."""

import pandas as pd

from config_reader import ler_token_config, enviar_csv_para_hevi
from contabit_client import consultar_todas_empresas, normalizar_nome

NOME_CSV = "departamentos_api.csv"


def coletar_departamentos_unicos():
    """
    Consulta lotações em todas as empresas do .config.
    Nomes repetidos entre empresas são ignorados (mantém o primeiro).
    """
    print("Coletando lotacoes Contabit (departamentos)...")
    por_empresa = consultar_todas_empresas("lotacao", com_mes_ano=False)

    nomes_vistos = set()
    departamentos = []
    ignorados = 0

    for id_empresa, lista in por_empresa:
        for item in lista:
            nome = (item.get("dsLotacao") or "").strip()
            if not nome:
                continue
            chave = normalizar_nome(nome)
            if chave in nomes_vistos:
                ignorados += 1
                continue
            nomes_vistos.add(chave)
            id_lotacao = item.get("idLotacao", "")
            departamentos.append(
                {
                    "campo_chave": "codigo_legado",
                    "codigo_legado": str(id_lotacao),
                    "nome": nome,
                    "conta": str(id_lotacao),
                    "id-empresa": str(id_empresa),
                }
            )

    print(
        f"Departamentos unicos: {len(departamentos)} | "
        f"duplicados ignorados: {ignorados}"
    )
    return departamentos


def gerar_csv_departamentos():
    print("=" * 70)
    print("GERACAO CSV DEPARTAMENTOS - Contabit /lotacao")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit do .config")
        return None

    departamentos = coletar_departamentos_unicos()
    if not departamentos:
        print("Nenhum departamento encontrado")
        return None

    df = pd.DataFrame(departamentos)
    df = df.sort_values("codigo_legado", key=lambda s: s.astype(str))
    df.to_csv(NOME_CSV, index=False, encoding="utf-8-sig", sep=";")
    print(f"CSV gerado: {NOME_CSV} ({len(df)} registros)")
    print(df.head(5).to_string())
    return NOME_CSV


def processar_integracao_completa():
    print("=" * 70)
    print("INTEGRACAO DEPARTAMENTOS - Contabit -> Hevi")
    print("=" * 70)

    arquivo = gerar_csv_departamentos()
    if not arquivo:
        return False

    ok = enviar_csv_para_hevi(arquivo, pag="configuracao_depto", usuario="gotech")
    if ok:
        print("Integracao de departamentos concluida com sucesso")
    else:
        print("Falha no envio de departamentos")
    return ok


if __name__ == "__main__":
    sucesso = processar_integracao_completa()
    raise SystemExit(0 if sucesso else 1)
