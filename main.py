#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE INTEGRAÇÃO COMPLETA
Contabit API → CSV → Sistema Hevi/ifPonto

Sequência:
1. Empresas (opcional)
2. Departamentos (lotação)
3. Cargos
4. Funcionários (trabalhador)
5. Afastamentos e Férias (único arquivo)
6. Demissões (REST)
"""

import sys
import os
import time
from datetime import datetime
import json

try:
    import empresas
    import departamentos
    import cargos
    import funcionarios
    import afastamentos
    import demissoes
    from config_reader import (
        ler_config,
        ler_token_config,
        ler_modulos_habilitados,
        CONFIG_PATH,
    )
except ImportError as e:
    print(f"ERRO: Nao foi possivel importar um dos modulos necessarios: {e}")
    sys.exit(1)


def imprimir_banner():
    banner = """
==============================================================================
                 SISTEMA DE INTEGRACAO COMPLETA
                      Contabit -> Hevi
------------------------------------------------------------------------------
  Sequencia:
    1. Empresas
    2. Departamentos (lotacao)
    3. Cargos
    4. Funcionarios (trabalhador)
    5. Afastamentos + Ferias
    6. Demissoes (REST)
==============================================================================
"""
    print(banner)


def verificar_prerequisitos():
    print("Verificando pre-requisitos...")
    erros = []

    if not os.path.exists(CONFIG_PATH):
        erros.append(f"Arquivo .config nao encontrado em {CONFIG_PATH}")
    else:
        print(f"Arquivo .config encontrado: {CONFIG_PATH}")
        config = ler_config()
        if not config:
            erros.append("Erro ao ler arquivo .config")
        else:
            for secao in ("APISOURCE", "APITARGET"):
                if secao not in config:
                    erros.append(f"Secao [{secao}] nao encontrada no .config")
                else:
                    print(f"Secao [{secao}] encontrada")

            token = ler_token_config()
            if not token:
                erros.append("Token Contabit nao encontrado em [APISOURCE]")
            else:
                print("Token Contabit encontrado")

            filtros = config.get("FILTROS", {})
            if not (filtros.get("codigo_empresa") or "").strip():
                erros.append("[FILTROS].codigo_empresa vazio (ex.: 233,384)")
            else:
                print(f"Empresas: {filtros.get('codigo_empresa')}")

    for modulo in ("requests", "pandas", "configparser", "pytz", "hashlib"):
        try:
            __import__(modulo)
            print(f"Modulo {modulo} disponivel")
        except ImportError:
            erros.append(f"Modulo Python '{modulo}' nao instalado")

    if erros:
        print("\nERROS ENCONTRADOS:")
        for erro in erros:
            print(f"   {erro}")
        return False

    print("Todos os pre-requisitos atendidos!")
    return True


def executar_modulo(nome_modulo, modulo, descricao):
    print(f"\n{'=' * 80}")
    print(f"EXECUTANDO: {nome_modulo.upper()} - {descricao}")
    print(f"{'=' * 80}")

    inicio = time.time()
    try:
        sucesso = modulo.processar_integracao_completa()
        duracao = time.time() - inicio
        resultado = {
            "modulo": nome_modulo,
            "descricao": descricao,
            "sucesso": sucesso,
            "duracao_segundos": round(duracao, 2),
            "timestamp": datetime.now().isoformat(),
        }
        status = "CONCLUIDO" if sucesso else "FALHOU"
        print(f"\n{nome_modulo.upper()} {status} ({duracao:.1f}s)")
        return resultado
    except Exception as e:
        duracao = time.time() - inicio
        print(f"\nERRO CRITICO em {nome_modulo.upper()}: {e}")
        return {
            "modulo": nome_modulo,
            "descricao": descricao,
            "sucesso": False,
            "erro": str(e),
            "duracao_segundos": round(duracao, 2),
            "timestamp": datetime.now().isoformat(),
        }


def pausar_entre_modulos(segundos=3):
    print(f"\nAguardando {segundos}s antes do proximo modulo...")
    time.sleep(segundos)


def gerar_relatorio_final(resultados):
    print(f"\n{'=' * 80}")
    print("RELATORIO FINAL DA INTEGRACAO")
    print(f"{'=' * 80}")

    executados = [r for r in resultados if not r.get("pulado")]
    pulados = [r for r in resultados if r.get("pulado")]
    sucessos = sum(1 for r in executados if r["sucesso"])
    falhas = sum(1 for r in executados if not r["sucesso"])
    tempo_total = sum(r["duracao_segundos"] for r in resultados)

    print(f"Sucesso: {sucessos}/{len(executados)} | Falhas: {falhas} | Pulados: {len(pulados)}")
    print(f"Tempo total: {tempo_total:.1f}s")

    for resultado in resultados:
        if resultado.get("pulado"):
            status = "PULADO"
        elif resultado["sucesso"]:
            status = "OK"
        else:
            status = "FALHA"
        print(
            f"  [{status}] {resultado['modulo']:<15} "
            f"({resultado['duracao_segundos']:5.1f}s)"
        )
        if not resultado["sucesso"] and not resultado.get("pulado") and "erro" in resultado:
            print(f"      Erro: {resultado['erro']}")

    relatorio = {
        "execucao": {
            "data_hora": datetime.now().isoformat(),
            "sucessos": sucessos,
            "falhas": falhas,
            "pulados": len(pulados),
            "tempo_total_segundos": tempo_total,
        },
        "modulos": resultados,
    }
    nome = f"relatorio_integracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(nome, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        print(f"Relatorio salvo: {nome}")
    except Exception as e:
        print(f"Erro ao salvar relatorio: {e}")

    print("\nArquivos gerados:")
    for arquivo in (
        "empresas_api.csv",
        "departamentos_api.csv",
        "cargos_api.csv",
        "funcionarios_api.csv",
        "afastamentos_api.csv",
        "demissoes_api.csv",
    ):
        if os.path.exists(arquivo):
            print(f"  OK  {arquivo} ({os.path.getsize(arquivo):,} bytes)")
        else:
            print(f"  --  {arquivo}")

    if len(executados) == 0:
        print("\nNenhum modulo habilitado em [MODULOS]")
        return False
    return falhas == 0


def main():
    try:
        imprimir_banner()
        if not verificar_prerequisitos():
            return False

        sequencia_modulos = [
            ("empresas", empresas, "Cadastro de Empresas"),
            ("departamentos", departamentos, "Cadastro de Departamentos"),
            ("cargos", cargos, "Cadastro de Cargos"),
            ("funcionarios", funcionarios, "Cadastro de Funcionarios"),
            ("afastamentos", afastamentos, "Afastamentos e Ferias"),
            ("demissoes", demissoes, "Demissoes (REST)"),
        ]

        modulos_cfg = ler_modulos_habilitados()
        print("\nModulos no .config [MODULOS]:")
        for nome, _, _ in sequencia_modulos:
            flag = "ON " if modulos_cfg.get(nome, True) else "OFF"
            print(f"  [{flag}] {nome}")

        resultados = []
        inicio_geral = time.time()

        for i, (nome_modulo, modulo, descricao) in enumerate(sequencia_modulos, 1):
            print(f"\nProgresso: {i}/{len(sequencia_modulos)}")
            if not modulos_cfg.get(nome_modulo, True):
                print(f"Pulando {nome_modulo} ([MODULOS]=false)")
                resultados.append(
                    {
                        "modulo": nome_modulo,
                        "descricao": descricao,
                        "sucesso": True,
                        "pulado": True,
                        "duracao_segundos": 0,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                continue

            resultados.append(executar_modulo(nome_modulo, modulo, descricao))
            if i < len(sequencia_modulos):
                pausar_entre_modulos(3)

        sucesso_geral = gerar_relatorio_final(resultados)
        print(f"\nTempo total: {time.time() - inicio_geral:.1f}s")
        return sucesso_geral

    except KeyboardInterrupt:
        print("\nIntegracao interrompida pelo usuario")
        return False
    except Exception as e:
        print(f"\nERRO CRITICO: {e}")
        return False


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        os.system("chcp 65001 > nul")
    sucesso = main()
    sys.exit(0 if sucesso else 1)
