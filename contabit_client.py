# -*- coding: utf-8 -*-
"""Cliente HTTP para a API Contabit (fonte da integração)."""

import time
from datetime import datetime

import requests

from config_reader import (
    obter_headers_contabit,
    ler_url_contabit,
    ler_codigos_empresa,
    mes_ano_atual,
)


def _extrair_lista(payload):
    """Normaliza resposta paginada Contabit ({data: [...]}) ou lista direta."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []


def consultar_contabit(endpoint, id_empresa, mes_ano=None, page_size=1000):
    """
    Consulta um endpoint Contabit com paginação.

    Args:
        endpoint: caminho relativo (ex.: 'cargo', 'trabalhador')
        id_empresa: código da empresa
        mes_ano: opcional, formato MM/YYYY
        page_size: tamanho da página

    Returns:
        list[dict]: registros em data[]
    """
    headers = obter_headers_contabit()
    if not headers:
        raise RuntimeError("Não foi possível obter headers Contabit do .config")

    base = ler_url_contabit().rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"
    registros = []
    page = 1

    while True:
        params = {
            "idEmpresa": int(id_empresa),
            "pageNumber": page,
            "pageSize": page_size,
        }
        if mes_ano:
            params["mesAno"] = mes_ano

        print(f"  Contabit {endpoint} empresa={id_empresa} pagina={page}...", end=" ")
        response = requests.get(url, headers=headers, params=params, timeout=60)

        if response.status_code != 200:
            raise RuntimeError(
                f"Contabit {endpoint} empresa={id_empresa}: "
                f"HTTP {response.status_code} — {response.text[:300]}"
            )

        payload = response.json()
        pagina_dados = _extrair_lista(payload)
        registros.extend(pagina_dados)
        print(f"{len(pagina_dados)} registro(s)")

        total_pages = 1
        if isinstance(payload, dict):
            total_pages = int(payload.get("totalPages") or 1)

        if page >= total_pages or not pagina_dados:
            break

        page += 1
        time.sleep(0.3)

    return registros


def consultar_todas_empresas(endpoint, com_mes_ano=False):
    """
    Consulta o endpoint para todas as empresas do .config.

    Returns:
        list[tuple[str, list]]: [(id_empresa, registros), ...]
    """
    empresas = ler_codigos_empresa()
    if not empresas:
        raise RuntimeError(
            "Nenhuma empresa em [FILTROS].codigo_empresa no .config "
            "(ex.: 233,384)"
        )

    mes_ano = mes_ano_atual() if com_mes_ano else None
    if com_mes_ano:
        print(f"Competência (mesAno): {mes_ano}")

    resultado = []
    for id_empresa in empresas:
        dados = consultar_contabit(endpoint, id_empresa, mes_ano=mes_ano)
        resultado.append((id_empresa, dados))
    return resultado


def formatar_data_brasileira(data_iso):
    """Converte ISO (YYYY-MM-DD...) para DD/MM/YYYY."""
    if not data_iso:
        return ""
    try:
        data_str = str(data_iso).replace("Z", "").split("T")[0]
        return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""


def formatar_cpf_11_digitos(cpf):
    """Mantém apenas dígitos e preenche com zeros à esquerda até 11."""
    if cpf is None:
        return ""
    digitos = "".join(ch for ch in str(cpf) if ch.isdigit())
    if not digitos:
        return ""
    return digitos.zfill(11)[-11:]


def formatar_cpf_mascarado(cpf):
    """CPF no formato 000.000.000-00."""
    digitos = formatar_cpf_11_digitos(cpf)
    if len(digitos) != 11:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def normalizar_nome(nome):
    """Normaliza nome para deduplicação (casefold + trim)."""
    return (nome or "").strip().casefold()


def codigo_cargo_unico(id_empresa, id_cargo):
    """
    Gera codigo_legado único concatenando empresa + idCargo Contabit.

    Ex.: empresa 233, cargo 8  → "2338"
         empresa 384, cargo 8  → "3848"
    """
    if id_empresa is None or id_cargo is None or str(id_cargo).strip() == "":
        return ""
    return f"{str(id_empresa).strip()}{str(id_cargo).strip()}"
