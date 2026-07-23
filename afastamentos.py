# -*- coding: utf-8 -*-
"""
Integração de afastamentos + férias (único CSV):
Contabit /afastamento → afastamentos_api.csv → Hevi (ponto_afastamento)

IDs Hevi vêm de [AFASTAMENTOS] no .config (ex.: 95 = 1011).
"""

import csv
from collections import Counter

from config_reader import ler_token_config, enviar_csv_para_hevi, ler_mapa_afastamentos
from contabit_client import (
    consultar_todas_empresas,
    formatar_cpf_mascarado,
    formatar_cpf_11_digitos,
    formatar_data_brasileira,
)

NOME_CSV = "afastamentos_api.csv"


def definir_id_afastamento(fl_motivo, mapa_afastamentos):
    """
    Resolve id-afastamento Hevi a partir do código Contabit e do .config.
    Retorna None se o código não estiver mapeado.
    """
    motivo = str(fl_motivo or "").strip()
    if not motivo:
        return None
    return mapa_afastamentos.get(motivo)


def mapear_afastamento_para_csv(item, mapa_afastamentos):
    ds_motivo = (item.get("dsMotivo") or "").strip()
    ds_obs = (item.get("dsObservacao") or "").strip()
    obs = ds_motivo
    if ds_obs:
        obs = f"{ds_motivo} | {ds_obs}" if ds_motivo else ds_obs
    if not obs:
        obs = "Afastamento"

    fl_motivo = item.get("flMotivoAfastamento")
    id_hevi = definir_id_afastamento(fl_motivo, mapa_afastamentos)
    if not id_hevi:
        return None

    cpf_mascarado = formatar_cpf_mascarado(item.get("nrCPF", ""))
    cpf_digitos = formatar_cpf_11_digitos(item.get("nrCPF", ""))

    return {
        "id-afastamento": id_hevi,
        "dtinicio": formatar_data_brasileira(item.get("dtAfastamento")),
        "dtfim": formatar_data_brasileira(item.get("dtRetorno")),
        "obs": obs,
        "campo_chave": "cpf",
        "cpf": cpf_mascarado or cpf_digitos,
        "_fl_motivo": str(fl_motivo or "").strip(),
    }


def converter_para_csv(dados, nome_arquivo=NOME_CSV):
    if not dados:
        print("Nao ha dados para converter em CSV")
        return None

    try:
        fieldnames = [k for k in dados[0].keys() if not k.startswith("_")]
        with open(nome_arquivo, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(dados)
        print(f"CSV gerado: {nome_arquivo} ({len(dados)} registros)")
        return nome_arquivo
    except Exception as e:
        print(f"Erro ao gerar CSV: {e}")
        return None


def gerar_csv_afastamentos():
    print("=" * 70)
    print("GERACAO CSV AFASTAMENTOS + FERIAS - Contabit")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit do .config")
        return None

    mapa = ler_mapa_afastamentos()
    if not mapa:
        print(
            "Nenhum mapeamento em [AFASTAMENTOS]. "
            "Adicione linhas como: 95 = 1011"
        )
        return None

    print("Mapeamento [AFASTAMENTOS] do .config:")
    for codigo, id_hevi in sorted(mapa.items(), key=lambda x: x[0]):
        print(f"  Contabit {codigo} -> Hevi {id_hevi}")

    por_empresa = consultar_todas_empresas("afastamento", com_mes_ano=True)
    registros = []
    ignorados = []
    contagem_ids = Counter()

    for id_empresa, lista in por_empresa:
        print(f"Empresa {id_empresa}: {len(lista)} afastamento(s)")
        for item in lista:
            row = mapear_afastamento_para_csv(item, mapa)
            if row is None:
                fl = str(item.get("flMotivoAfastamento") or "").strip()
                ds = (item.get("dsMotivo") or "").strip()
                ignorados.append((fl, ds, item.get("nmNome")))
                continue
            contagem_ids[row["id-afastamento"]] += 1
            registros.append(row)

    if ignorados:
        print(
            f"\nAVISO: {len(ignorados)} registro(s) ignorado(s) "
            f"(codigo Contabit sem mapeamento no .config):"
        )
        por_codigo = Counter(fl for fl, _, _ in ignorados)
        for fl, qtd in sorted(por_codigo.items()):
            exemplo = next(ds for f, ds, _ in ignorados if f == fl)
            print(f"  {fl} ({qtd}x) — {exemplo}")
            print(f"    Adicione no .config: {fl} = <id_hevi>")

    if not registros:
        print("Nenhum afastamento mapeado para exportar")
        return None

    print("\nTotais por id-afastamento Hevi:")
    for id_hevi, qtd in sorted(contagem_ids.items()):
        print(f"  {id_hevi}: {qtd}")

    return converter_para_csv(registros, NOME_CSV)


def processar_integracao_completa():
    print("=" * 70)
    print("INTEGRACAO AFASTAMENTOS+FERIAS - Contabit -> Hevi")
    print("=" * 70)

    arquivo = gerar_csv_afastamentos()
    if not arquivo:
        return False

    ok = enviar_csv_para_hevi(arquivo, pag="ponto_afastamento")
    if ok:
        print("Integracao de afastamentos concluida com sucesso")
    else:
        print("Falha no envio de afastamentos")
    return ok


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1].lower() == "csv":
        ok = bool(gerar_csv_afastamentos())
    else:
        ok = processar_integracao_completa()
    raise SystemExit(0 if ok else 1)
