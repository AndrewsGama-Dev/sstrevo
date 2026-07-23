# -*- coding: utf-8 -*-
"""Integração de cargos: Contabit /cargo → cargos_api.csv → Hevi."""

import pandas as pd

from config_reader import ler_token_config, enviar_csv_para_hevi
from contabit_client import consultar_todas_empresas, normalizar_nome

NOME_CSV = "cargos_api.csv"


def coletar_cargos_unicos():
    """
    Consulta cargos em todas as empresas do .config.
    Nomes repetidos entre empresas são ignorados (mantém o primeiro).
    """
    print("Coletando cargos Contabit...")
    por_empresa = consultar_todas_empresas("cargo", com_mes_ano=False)

    nomes_vistos = set()
    cargos = []
    ignorados = 0

    for id_empresa, lista in por_empresa:
        for item in lista:
            nome = (item.get("dsCargo") or "").strip()
            if not nome:
                continue
            chave = normalizar_nome(nome)
            if chave in nomes_vistos:
                ignorados += 1
                continue
            nomes_vistos.add(chave)
            id_cargo = item.get("idCargo", "")
            cargos.append(
                {
                    "campo_chave": "codigo_legado",
                    "codigo_legado": str(id_cargo),
                    "nome": nome,
                    "id-empresa": str(id_empresa),
                    "nome_cbo": "",
                    "nro_cbo": "",
                }
            )

    print(f"Cargos unicos: {len(cargos)} | duplicados ignorados: {ignorados}")
    return cargos


def gerar_csv_cargos():
    print("=" * 70)
    print("GERACAO CSV CARGOS - Contabit")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit do .config")
        return None

    cargos = coletar_cargos_unicos()
    if not cargos:
        print("Nenhum cargo encontrado")
        return None

    df = pd.DataFrame(cargos)
    df = df.sort_values("codigo_legado", key=lambda s: s.astype(str))
    df.to_csv(NOME_CSV, index=False, encoding="utf-8-sig", sep=";")
    print(f"CSV gerado: {NOME_CSV} ({len(df)} registros)")
    print(df.head(5).to_string())
    return NOME_CSV


def processar_integracao_completa():
    print("=" * 70)
    print("INTEGRACAO CARGOS - Contabit -> Hevi")
    print("=" * 70)

    arquivo = gerar_csv_cargos()
    if not arquivo:
        return False

    ok = enviar_csv_para_hevi(arquivo, pag="configuracao_cargo", usuario="gotech")
    if ok:
        print("Integracao de cargos concluida com sucesso")
    else:
        print("Falha no envio de cargos")
    return ok


if __name__ == "__main__":
    sucesso = processar_integracao_completa()
    raise SystemExit(0 if sucesso else 1)
