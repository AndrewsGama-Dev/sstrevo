# -*- coding: utf-8 -*-
import configparser
import hashlib
import os
from datetime import datetime

import pytz


def ler_config():
    """
    Lê o arquivo .config e retorna um dicionário com todas as seções.
    """
    try:
        if not os.path.exists(".config"):
            print("Arquivo .config nao encontrado")
            return None

        config = configparser.ConfigParser()
        config.read(".config", encoding="utf-8")

        config_dict = {}
        for secao in config.sections():
            config_dict[secao] = dict(config[secao])

        return config_dict

    except Exception as e:
        print(f"Erro ao ler arquivo .config: {e}")
        return None


def ler_token_config():
    """
    Lê o token da fonte (Contabit) em [APISOURCE].
    """
    try:
        config = ler_config()
        if config and "APISOURCE" in config:
            token = config["APISOURCE"].get("token")
            if token:
                print("Token Contabit carregado do arquivo .config")
                return token.strip().strip('"').strip("'")

        print("Token nao encontrado na secao [APISOURCE]")
        return None

    except Exception as e:
        print(f"Erro ao ler token: {e}")
        return None


def ler_url_contabit():
    """URL base da API Contabit (default: https://dalloglio.contabit.com.br/api)."""
    config = ler_config()
    default = "https://dalloglio.contabit.com.br/api"
    if not config or "APISOURCE" not in config:
        return default
    url = (config["APISOURCE"].get("url") or "").strip().strip('"').strip("'")
    return url.rstrip("/") if url else default


def obter_headers_contabit():
    """Headers para chamadas à API Contabit (Authorization = token puro, sem Bearer)."""
    token = ler_token_config()
    if not token:
        return None
    return {
        "Accept": "application/json",
        "Authorization": token,
    }


# Compatibilidade com imports antigos
def obter_headers_api():
    return obter_headers_contabit()


def ler_codigos_empresa():
    """
    Lê lista de IDs de empresa em [FILTROS].codigo_empresa.

    Aceita um ou vários códigos separados por vírgula (ex.: 233,384).
    """
    try:
        config = ler_config()
        if not config or "FILTROS" not in config:
            return []

        bruto = (config["FILTROS"].get("codigo_empresa") or "").strip().strip('"')
        if not bruto:
            return []

        codigos = []
        for parte in bruto.replace(";", ",").split(","):
            codigo = parte.strip()
            if codigo:
                codigos.append(codigo)
        return codigos
    except Exception as e:
        print(f"Erro ao ler codigo_empresa do .config: {e}")
        return []


def ler_codigo_empresa_filtro():
    """
    Compatibilidade: retorna o primeiro código de empresa ou None.
    Preferir ler_codigos_empresa() para multi-empresa.
    """
    codigos = ler_codigos_empresa()
    return codigos[0] if codigos else None


def mes_ano_atual():
    """Competência atual no formato MM/YYYY (ex.: 07/2026)."""
    return datetime.now().strftime("%m/%Y")


def ler_mapa_afastamentos():
    """
    Lê [AFASTAMENTOS] do .config: codigo Contabit → id Hevi.

    Exemplo no .config:
        [AFASTAMENTOS]
        95 = 1011
        58 = 1012

    Returns:
        dict[str, str]: {"95": "1011", ...}
    """
    mapa = {}
    try:
        config = ler_config()
        if not config or "AFASTAMENTOS" not in config:
            print(
                "AVISO: secao [AFASTAMENTOS] nao encontrada no .config "
                "(ex.: 95 = 1011)"
            )
            return mapa

        for codigo, id_hevi in config["AFASTAMENTOS"].items():
            codigo_limpo = str(codigo).strip().strip('"').strip("'")
            id_limpo = str(id_hevi).strip().strip('"').strip("'")
            if not codigo_limpo or not id_limpo or id_limpo == "?":
                continue
            mapa[codigo_limpo] = id_limpo

        return mapa
    except Exception as e:
        print(f"Erro ao ler [AFASTAMENTOS] do .config: {e}")
        return mapa


def carregar_configuracoes_target():
    """Carrega [APITARGET] do .config."""
    try:
        config = ler_config()
        if not config or "APITARGET" not in config:
            print("Secao [APITARGET] nao encontrada no arquivo .config")
            return None

        secao = config["APITARGET"]
        return {
            "url": (secao.get("url") or "").strip().strip('"'),
            "integracao": (secao.get("integracao") or "").strip().strip('"'),
            "token_base": (secao.get("token_base") or "").strip().strip('"'),
            "campo_chave": (secao.get("campo_chave") or "cpf").strip().strip('"'),
            "pag_demissao": (secao.get("pag_demissao") or "funcionario_demissao")
            .strip()
            .strip('"'),
        }
    except Exception as e:
        print(f"Erro ao carregar [APITARGET]: {e}")
        return None


def gerar_token_target():
    """
    Gera token diário SHA256 para a API de destino (Hevi/ifPonto).

    Returns:
        tuple: (config_target dict, token_final) ou (None, None)
    """
    config_target = carregar_configuracoes_target()
    if not config_target:
        return None, None

    tz_sao_paulo = pytz.timezone("America/Sao_Paulo")
    data_atual = datetime.now(tz_sao_paulo).strftime("%d/%m/%Y")
    token_concatenado = config_target["token_base"] + data_atual
    token_final = hashlib.sha256(token_concatenado.encode("utf-8")).hexdigest()

    print(f"Data atual (SP): {data_atual}")
    print(f"Token destino gerado: {token_final[:32]}...")
    return config_target, token_final


def enviar_csv_para_hevi(nome_arquivo_csv, pag, usuario=None, timeout=90):
    """
    POST multipart padrão para importação no Hevi/ifPonto.
    """
    import requests

    if not os.path.exists(nome_arquivo_csv):
        print(f"Arquivo {nome_arquivo_csv} nao encontrado!")
        return False

    config_target, token_final = gerar_token_target()
    if not config_target or not token_final:
        print("Falha ao gerar token para API de destino")
        return False

    usuario_envio = usuario or config_target["integracao"] or "gotech"
    headers = {"user": usuario_envio, "token": token_final}
    data = {"pag": pag, "cmd": "importar_cad", "separador": ";"}

    try:
        print(f"Enviando POST — pag={pag} user={usuario_envio}")
        print(f"URL: {config_target['url']}")
        with open(nome_arquivo_csv, "rb") as arquivo:
            files = {"arquivo": (nome_arquivo_csv, arquivo, "text/csv")}
            response = requests.post(
                config_target["url"],
                data=data,
                files=files,
                headers=headers,
                timeout=timeout,
            )

        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Resposta: {response.text[:500]}")
            return False

        try:
            resultado = response.json()
        except ValueError:
            print(f"Resposta nao e JSON: {response.text[:500]}")
            return False

        if resultado.get("success") is False:
            print(f"API retornou erro: {resultado}")
            return False

        print(f"POST ok — resposta: {resultado}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisicao destino: {e}")
        return False


def _parse_bool_config(valor, default=True):
    """Interpreta true/false, 1/0, sim/nao, yes/no (case insensitive)."""
    if valor is None:
        return default
    texto = str(valor).strip().strip('"').lower()
    if texto in ("true", "1", "yes", "y", "sim", "s", "on"):
        return True
    if texto in ("false", "0", "no", "n", "nao", "não", "off"):
        return False
    return default


MODULOS_PADRAO = (
    "empresas",
    "departamentos",
    "cargos",
    "funcionarios",
    "afastamentos",
    "demissoes",
)


def ler_modulos_habilitados():
    """
    Lê a seção [MODULOS] do .config (true/false por módulo).

    Se a seção não existir, todos os módulos ficam habilitados (compatibilidade).
    """
    habilitados = {nome: True for nome in MODULOS_PADRAO}
    try:
        config = ler_config()
        if not config or "MODULOS" not in config:
            return habilitados

        secao = config["MODULOS"]
        for nome in MODULOS_PADRAO:
            if nome in secao:
                habilitados[nome] = _parse_bool_config(secao.get(nome), default=True)
        return habilitados
    except Exception as e:
        print(f"Erro ao ler [MODULOS] do .config: {e}")
        return habilitados


def modulo_habilitado(nome_modulo):
    """Retorna True se o módulo deve ser executado conforme [MODULOS]."""
    return bool(ler_modulos_habilitados().get(nome_modulo, True))
