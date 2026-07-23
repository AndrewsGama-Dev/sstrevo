# -*- coding: utf-8 -*-
"""Integração de funcionários: Contabit /trabalhador → funcionarios_api.csv → Hevi."""

import os
import tempfile
from datetime import datetime

import pandas as pd

from config_reader import (
    ler_token_config,
    enviar_csv_para_hevi,
    carregar_configuracoes_target,
)

from contabit_client import (
    consultar_todas_empresas,
    consultar_contabit,
    formatar_cpf_11_digitos,
    formatar_data_brasileira,
)

# Reexport para módulos que importavam destes helpers
from config_reader import gerar_token_target  # noqa: F401

NOME_CSV = "funcionarios_api.csv"


def ler_campo_chave_funcionario():
    """Lê [APITARGET].campo_chave do .config (padrão: cpf)."""
    cfg = carregar_configuracoes_target()
    if cfg:
        chave = (cfg.get("campo_chave") or "").strip().strip('"').strip("'")
        if chave:
            return chave.lower()
    return "cpf"


def formatar_sexo(fl_sexo):
    """M/F da Contabit → Masculino/Feminino."""
    valor = (fl_sexo or "").strip().upper()
    if valor == "M":
        return "Masculino"
    if valor == "F":
        return "Feminino"
    return (fl_sexo or "").strip()


def salvar_dataframe_csv_funcionarios(df, nome_preferido=NOME_CSV):
    """Grava CSV; se bloqueado, tenta nome alternativo / temp."""
    base, ext = os.path.splitext(nome_preferido)
    if not ext:
        ext = ".csv"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidatos = [
        nome_preferido,
        f"{base}_{stamp}{ext}",
        os.path.join(tempfile.gettempdir(), f"{base}_{stamp}{ext}"),
    ]

    ultimo_erro = None
    for caminho in candidatos:
        try:
            df.to_csv(caminho, index=False, encoding="utf-8-sig", sep=";")
            if caminho != nome_preferido:
                print(f"CSV salvo em caminho alternativo: {os.path.abspath(caminho)}")
            else:
                print(f"CSV gerado: {caminho}")
            return caminho
        except (PermissionError, OSError) as e:
            ultimo_erro = e
            continue

    print(f"Nao foi possivel gravar o CSV: {ultimo_erro}")
    return None


def montar_mapa_cargo(id_empresa):
    """Mapa idCargo → nome para uma empresa."""
    cargos = consultar_contabit("cargo", id_empresa)
    return {
        item.get("idCargo"): (item.get("dsCargo") or "").strip() for item in cargos
    }


def mapear_trabalhador_para_csv(
    item, id_empresa, mapa_cargo, campo_chave="cpf"
):
    cpf = formatar_cpf_11_digitos(item.get("nrCPF", ""))
    matricula = str(item.get("nrMatricula") or "").strip()
    id_cargo = item.get("idCargo")
    nome_cargo = mapa_cargo.get(id_cargo, "")

    telefone = item.get("nrTelefoneCelular") or item.get("nrTelefoneFixo") or ""
    endereco_partes = [
        (item.get("flLogradouro") or "").strip(),
        (item.get("dsLogradouro") or "").strip(),
        (item.get("nrLogradouro") or "").strip(),
    ]
    endereco = " ".join(p for p in endereco_partes if p).strip()

    return {
        "campo_chave": campo_chave,
        "nome": (item.get("nmNome") or "").strip(),
        "cpf": cpf,
        "matricula": matricula,
        "rg": item.get("nrRG") or "",
        "pis": item.get("nrPIS") or cpf,
        "dtadmissao": formatar_data_brasileira(item.get("dtAdmissao")),
        "cnh": "",
        "email": "",
        "nome_tipo_pessoa": "",
        "telefone": telefone or "",
        "ramal": "",
        "endereco": endereco,
        "bairro": item.get("nmBairro") or "",
        "cidade": item.get("nmCidade") or "",
        "uf": item.get("flUF") or "",
        "cep": item.get("nrCEP") or "",
        "login": cpf,
        "cod_empresa": str(id_empresa),
        "codigo_legado_empresa": str(id_empresa),
        "dtdemissao": formatar_data_brasileira(item.get("dtDesligamento")),
        "regime_juridico": "",
        "tipo_salario": "",
        "salario": "",
        "dtnascimento": formatar_data_brasileira(item.get("dtNascimento")),
        "nome_mae": "",
        "nome_pai": "",
        "escolaridade": "",
        "estado_civil": "",
        "qtd_filho": "",
        "sexo": formatar_sexo(item.get("flSexo")),
        "nacionalidade": "",
        "naturalidade": "",
        "complemento": item.get("dsCpLogradouro") or "",
        "codigo_cargo": str(id_cargo) if id_cargo is not None else "",
        "nome_cargo": nome_cargo,
        "senha": "Ponto123",
        "cracha": cpf,
        "nome_nivel": "",
        "cod_escala_padrao": "",
        "codigo_escala": "",
        "dtinicio_escala": "",
        "empresa": "",
        "nome_funcao": nome_cargo,
        "codigo_legado_funcao": str(id_cargo) if id_cargo is not None else "",
        "cod_sindicato": "",
        "nome_sindicato": "",
        "orgao_emissor_rg": "",
    }


def gerar_csv_funcionarios():
    print("=" * 70)
    print("GERACAO CSV FUNCIONARIOS - Contabit /trabalhador")
    print("=" * 70)

    if not ler_token_config():
        print("Falha ao carregar token Contabit do .config")
        return None

    campo_chave = ler_campo_chave_funcionario()
    print(f"campo_chave (.config): {campo_chave}")

    por_empresa = consultar_todas_empresas("trabalhador", com_mes_ano=True)
    funcionarios = []
    mapas_cache = {}

    for id_empresa, lista in por_empresa:
        if id_empresa not in mapas_cache:
            print(f"Carregando mapa de cargos empresa {id_empresa}...")
            mapas_cache[id_empresa] = montar_mapa_cargo(id_empresa)
        mapa_cargo = mapas_cache[id_empresa]

        for item in lista:
            # Inclui ativos do mês; se já desligado, ainda pode vir na consulta —
            # mantém dtdemissao preenchida quando houver.
            funcionarios.append(
                mapear_trabalhador_para_csv(
                    item, id_empresa, mapa_cargo, campo_chave
                )
            )

    if not funcionarios:
        print("Nenhum trabalhador encontrado")
        return None

    df = pd.DataFrame(funcionarios)
    arquivo = salvar_dataframe_csv_funcionarios(df)
    if not arquivo:
        return None

    print(f"Total funcionarios: {len(df)}")
    print(df.head(3).to_string())
    return arquivo


def validar_dados_csv(nome_arquivo):
    if not nome_arquivo:
        return
    try:
        df = pd.read_csv(nome_arquivo, sep=";", encoding="utf-8-sig")
        print(f"Validacao: {len(df)} registros, {len(df.columns)} colunas")
        for campo in ("nome", "cpf", "matricula"):
            if campo in df.columns:
                vazios = int((df[campo].isna() | (df[campo].astype(str) == "")).sum())
                print(f"  {campo}: {vazios} vazios")
    except Exception as e:
        print(f"Erro na validacao: {e}")


def processar_apenas_exportacao_csv():
    arquivo = gerar_csv_funcionarios()
    if not arquivo:
        return False
    validar_dados_csv(arquivo)
    return True


def processar_integracao_completa():
    print("=" * 70)
    print("INTEGRACAO FUNCIONARIOS - Contabit -> Hevi")
    print("=" * 70)

    arquivo = gerar_csv_funcionarios()
    if not arquivo:
        return False

    validar_dados_csv(arquivo)
    ok = enviar_csv_para_hevi(arquivo, pag="funcionario_cadastrar")
    if ok:
        print("Integracao de funcionarios concluida com sucesso")
    else:
        print("Falha no envio de funcionarios")
    return ok


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1].lower() in ("csv", "exportar"):
        ok = processar_apenas_exportacao_csv()
    else:
        ok = processar_integracao_completa()
    raise SystemExit(0 if ok else 1)
