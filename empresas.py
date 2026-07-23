# -*- coding: utf-8 -*-
"""Integração de empresas: Contabit /empresa → empresas_api.csv → Hevi.

Módulo opcional ([MODULOS] empresas=false por padrão).
"""

import pandas as pd
import requests

from config_reader import (
    ler_token_config,
    obter_headers_contabit,
    ler_url_contabit,
    enviar_csv_para_hevi,
)

NOME_CSV = "empresas_api.csv"


def consultar_empresas_contabit():
    headers = obter_headers_contabit()
    if not headers:
        raise RuntimeError("Headers Contabit indisponiveis")

    url = f"{ler_url_contabit().rstrip('/')}/empresa"
    print(f"Consultando empresas Contabit: {url}")
    response = requests.get(url, headers=headers, params={"pageSize": 1000}, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    payload = response.json()
    if isinstance(payload, dict):
        return payload.get("data") or []
    if isinstance(payload, list):
        return payload
    return []


def mapear_empresa_para_csv(item):
    digitos = "".join(ch for ch in str(item.get("nrCNPJCPF") or "") if ch.isdigit())
    cnpj = digitos.zfill(14)[-14:] if digitos else ""

    return {
        "codigo_legado": str(item.get("idEmpresa") or ""),
        "campo_chave": "codigo_legado",
        "nro": str(item.get("idEmpresa") or ""),
        "nome": (item.get("nmRazaoSocial") or item.get("nmFantasia") or "").strip(),
        "cnpj": cnpj,
        "inscricao_estadual": "",
        "cep": item.get("nrCEP") or "",
        "endereco": " ".join(
            p
            for p in (
                item.get("flLogradouro") or "",
                item.get("dsLogradouro") or "",
                item.get("nrLogradouro") or "",
            )
            if p
        ).strip(),
        "bairro": item.get("nmBairro") or "",
        "cidade": item.get("nmCidade") or "",
        "uf": item.get("flUF") or "",
        "telefone": item.get("nrTelefoneFixo")
        or item.get("nrTelefoneCelular")
        or "",
        "email": item.get("nmEmail") or "",
        "site": "",
        "nome_relatorio": (
            item.get("nmFantasia") or item.get("nmRazaoSocial") or ""
        ).strip(),
    }


def gerar_csv_empresas():
    print("=" * 70)
    print("GERACAO CSV EMPRESAS - Contabit")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit")
        return None

    lista = consultar_empresas_contabit()
    if not lista:
        print("Nenhuma empresa encontrada")
        return None

    rows = [mapear_empresa_para_csv(item) for item in lista]
    df = pd.DataFrame(rows)
    df.to_csv(NOME_CSV, index=False, encoding="utf-8-sig", sep=";")
    print(f"CSV gerado: {NOME_CSV} ({len(df)} registros)")
    return NOME_CSV


def processar_integracao_completa():
    arquivo = gerar_csv_empresas()
    if not arquivo:
        return False
    return enviar_csv_para_hevi(arquivo, pag="configuracao_empresa", usuario="gotech")


if __name__ == "__main__":
    ok = processar_integracao_completa()
    raise SystemExit(0 if ok else 1)
