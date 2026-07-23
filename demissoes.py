# -*- coding: utf-8 -*-
"""
Integração de demissões via REST (sem SOAP):
Contabit /desligamento → demissoes_api.csv → Hevi (funcionario_demissao)

Campo chave: CPF formatado 000.000.000-00
"""

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import requests

from config_reader import (
    ler_token_config,
    ler_config,
    gerar_token_target,
)
from contabit_client import (
    consultar_todas_empresas,
    formatar_cpf_11_digitos,
    formatar_cpf_mascarado,
    formatar_data_brasileira,
)

NOME_ARQUIVO_CSV = "demissoes_api.csv"
ARQUIVO_HISTORICO_CPF = "demissoes_cpf_processados.txt"

COLUNAS_CSV_DEMISSOES = [
    "campo_chave",
    "cpf",
    "matricula",
    "nome",
    "DATA_DEMISSAO",
    "obs",
    "data_aviso",
    "data_ultimo_dia_trabalhado",
    "data_acerto",
    "motivo",
    "local_exame",
    "opcao_empregado",
    "tipo_aviso",
    "devolveu_cracha",
    "dias_indenizados",
    "data_exame",
]


def ler_pag_demissao_rest():
    cfg = ler_config()
    if not cfg or "APITARGET" not in cfg:
        return "funcionario_demissao"
    pag = (cfg["APITARGET"].get("pag_demissao") or "").strip().strip('"').strip("'")
    return pag if pag else "funcionario_demissao"


def carregar_cpfs_processados():
    if not os.path.exists(ARQUIVO_HISTORICO_CPF):
        return set()
    cpfs = set()
    try:
        with open(ARQUIVO_HISTORICO_CPF, "r", encoding="utf-8") as f:
            for linha in f:
                norm = formatar_cpf_11_digitos(linha.strip())
                if len(norm) == 11:
                    cpfs.add(norm)
    except OSError as e:
        print(f"AVISO: nao foi possivel ler {ARQUIVO_HISTORICO_CPF}: {e}")
    return cpfs


def registrar_cpfs_processados(cpfs_novos):
    novos = []
    for c in cpfs_novos:
        norm = formatar_cpf_11_digitos(str(c))
        if len(norm) == 11:
            novos.append(norm)
    if not novos:
        return
    atual = carregar_cpfs_processados()
    atual.update(novos)
    try:
        with open(ARQUIVO_HISTORICO_CPF, "w", encoding="utf-8") as f:
            for c in sorted(atual):
                f.write(c + "\n")
        print(
            f"Historico CPF demissao atualizado (+{len(novos)}): "
            f"{ARQUIVO_HISTORICO_CPF} ({len(atual)} total)"
        )
    except OSError as e:
        print(f"ERRO ao gravar historico CPF: {e}")


def calcular_datas_demissao(data_rescisao_iso):
    if not data_rescisao_iso:
        hoje = datetime.now()
        data_dem = hoje.strftime("%d/%m/%Y")
        return data_dem, data_dem

    data_dem = formatar_data_brasileira(data_rescisao_iso)
    return data_dem, data_dem


def mapear_desligamento_para_csv(item):
    cpf_mascarado = formatar_cpf_mascarado(item.get("nrCPF", ""))
    data_dem, data_ultimo = calcular_datas_demissao(item.get("dtRescisao"))
    motivo = (item.get("dsMotivo") or "Demissao").strip()

    return {
        "campo_chave": "cpf",
        "cpf": cpf_mascarado,
        "matricula": "",
        "nome": (item.get("nmNome") or "").strip(),
        "DATA_DEMISSAO": data_dem,
        "obs": motivo,
        "data_aviso": "",
        "data_ultimo_dia_trabalhado": data_ultimo,
        "data_acerto": "",
        "motivo": motivo,
        "local_exame": "",
        "opcao_empregado": "",
        "tipo_aviso": "",
        "devolveu_cracha": "Sim",
        "dias_indenizados": 0,
        "data_exame": "",
        "_cpf_digitos": formatar_cpf_11_digitos(item.get("nrCPF", "")),
    }


def analisar_resultado_rest_demissoes(resultado):
    if resultado.get("success") is False:
        return False

    ok_count = int(resultado.get("ok") or 0)
    ja_cad = int(resultado.get("ja_cad") or 0)
    erros_api = resultado.get("erros") or []
    info = (resultado.get("info") or "").strip()

    if info:
        print(f"Resumo API: {info}")
    if ok_count:
        print(f"{ok_count} registro(s) cadastrado(s).")
    if ja_cad:
        print(f"{ja_cad} registro(s) ja existiam.")
    if erros_api:
        print(f"AVISO: {len(erros_api)} mensagem(ns) em erros[]")
        for item in erros_api[:5]:
            print(f"   - {item}")
    return True


def enviar_csv_demissoes_rest(nome_arquivo_csv=NOME_ARQUIVO_CSV):
    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} nao encontrado!")
        return False

    config_target, token_final = gerar_token_target()
    if not config_target or not token_final:
        print("Falha ao gerar token para API de destino")
        return False

    pag = ler_pag_demissao_rest()
    usuario = config_target["integracao"]
    headers = {"user": usuario, "token": token_final}
    data = {"pag": pag, "cmd": "importar_cad", "separador": ";"}

    try:
        print(f"Enviando demissoes REST — pag={pag}")
        print(f"URL: {config_target['url']}")
        with open(nome_arquivo_csv, "rb") as arquivo:
            files = {"arquivo": (nome_arquivo_csv, arquivo, "text/csv")}
            response = requests.post(
                config_target["url"],
                data=data,
                files=files,
                headers=headers,
                timeout=90,
            )

        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Resposta: {response.text[:500]}")
            return False

        try:
            resultado = response.json()
        except ValueError:
            print(f"Resposta nao JSON: {response.text[:500]}")
            return False

        if resultado.get("success") is False:
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            return False

        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return analisar_resultado_rest_demissoes(resultado)
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisicao: {e}")
        return False


def gerar_csv_demissoes():
    print("=" * 70)
    print("GERACAO CSV DEMISSOES - Contabit /desligamento (REST)")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit do .config")
        return None

    ja_processados = carregar_cpfs_processados()
    print(f"CPFs ja processados no historico: {len(ja_processados)}")

    por_empresa = consultar_todas_empresas("desligamento", com_mes_ano=True)
    linhas = []
    cpfs_novos = []
    ignorados_historico = 0

    for id_empresa, lista in por_empresa:
        print(f"Empresa {id_empresa}: {len(lista)} desligamento(s)")
        for item in lista:
            row = mapear_desligamento_para_csv(item)
            cpf_dig = row.pop("_cpf_digitos", "")
            if not row.get("cpf"):
                print(f"  Ignorado sem CPF: {row.get('nome')}")
                continue
            if cpf_dig in ja_processados:
                ignorados_historico += 1
                continue
            linhas.append(row)
            if cpf_dig:
                cpfs_novos.append(cpf_dig)

    if not linhas:
        print(
            f"Nenhuma demissao nova para exportar "
            f"(ignoradas por historico: {ignorados_historico})"
        )
        df_vazio = pd.DataFrame(columns=COLUNAS_CSV_DEMISSOES)
        df_vazio.to_csv(NOME_ARQUIVO_CSV, index=False, encoding="utf-8-sig", sep=";")
        return NOME_ARQUIVO_CSV

    df = pd.DataFrame(linhas, columns=COLUNAS_CSV_DEMISSOES)
    df.to_csv(NOME_ARQUIVO_CSV, index=False, encoding="utf-8-sig", sep=";")
    registrar_cpfs_processados(cpfs_novos)
    print(
        f"CSV gerado: {NOME_ARQUIVO_CSV} ({len(df)} registros, "
        f"ignorados historico={ignorados_historico})"
    )
    print(df.head(5).to_string())
    return NOME_ARQUIVO_CSV


def processar_integracao_completa():
    """Fluxo único: Contabit → CSV → REST Hevi. SOAP removido."""
    print("=" * 70)
    print("INTEGRACAO DEMISSOES - Contabit -> Hevi (REST)")
    print("=" * 70)

    arquivo = gerar_csv_demissoes()
    if not arquivo:
        return False

    # CSV só com cabeçalho (sem linhas novas) → não envia
    try:
        df = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig")
        if df.empty:
            print("Sem demissoes novas — envio REST omitido")
            return True
    except Exception:
        pass

    ok = enviar_csv_demissoes_rest(arquivo)
    if ok:
        print("Integracao de demissoes concluida com sucesso")
    else:
        print("Falha no envio REST de demissoes")
    return ok


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1].lower() == "csv":
        ok = bool(gerar_csv_demissoes())
    else:
        ok = processar_integracao_completa()
    raise SystemExit(0 if ok else 1)
