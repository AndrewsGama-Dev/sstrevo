# Deploy e atualização no servidor (VPS Hostinger)

Integração **Contabit → Hevi/ifPonto** (projeto Python **sstrevo**).

| Item | Valor |
|------|--------|
| Caminho no servidor | `/home/gogotech/integracao/sstrevo` |
| Repositório | https://github.com/AndrewsGama-Dev/sstrevo.git |
| Fonte | API Contabit |
| Destino | Hevi/ifPonto (`[APITARGET]` no `.config`) |
| Orquestrador | `main.py` / `integrador.sh` |

## 1. Antes de atualizar

- Fazer **backup** do `.config` de produção (tokens e mapeamentos).
- Confirmar como a integração dispara hoje (**cron** no Linux).

## 2. O que vai no servidor

**Código (via Git):**

- `main.py`, `integrador.sh`, `config_reader.py`, `contabit_client.py`
- Módulos: `empresas.py`, `departamentos.py`, `cargos.py`, `funcionarios.py`, `afastamentos.py`, `demissoes.py`
- `requirements.txt`, `.gitignore`, este `DEPLOY_SERVIDOR.md`

**Não versionar (criar só no servidor):**

- **`.config`** — token Contabit, token Hevi, empresas, mapeamento de afastamentos
- `.venv/`
- CSVs gerados (`*_api.csv`), logs (`integrador.log`), histórico `demissoes_cpf_processados.txt`

## 3. Estrutura do `.config` (produção)

Criar em `/home/gogotech/integracao/sstrevo/.config`:

```ini
[APISOURCE]
url = https://dalloglio.contabit.com.br/api
token = "SEU_TOKEN_CONTABIT"

[FILTROS]
codigo_empresa = 233,384

[MODULOS]
empresas = false
departamentos = true
cargos = true
funcionarios = true
afastamentos = true
demissoes = true

[APITARGET]
url = https://stou.ifractal.com.br/sstrevo/rest/
integracao = gotech
token_base = SEU_TOKEN_BASE_HEVI
campo_chave = cpf
pag_demissao = funcionario_demissao

[AFASTAMENTOS]
# Contabit flMotivoAfastamento = ID Hevi
95 = 95
52 = 52
54 = 54
58 = 58
70 = 70
```

Auth Contabit: header `Authorization: <token>` (sem `Bearer`).  
`mesAno` em trabalhador/desligamento/afastamento: **sempre o mês atual**.

## 4. Primeira instalação no VPS

```bash
mkdir -p /home/gogotech/integracao/sstrevo
cd /home/gogotech/integracao/sstrevo

# Clone direto na pasta (evita sstrevo/sstrevo)
git clone https://github.com/AndrewsGama-Dev/sstrevo.git .

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

# No Linux, o requirements.txt pode falhar por pacotes Windows.
# Instale o mínimo necessário:
pip install requests pandas pytz

chmod +x integrador.sh

# Criar o .config (não vem do Git)
nano .config
```

Se a pasta já tiver `.venv` e o `git clone .` falhar (“not an empty directory”):

```bash
cd /home/gogotech/integracao/sstrevo
mv .venv /tmp/sstrevo_venv_backup
git clone https://github.com/AndrewsGama-Dev/sstrevo.git .
mv /tmp/sstrevo_venv_backup .venv
source .venv/bin/activate
pip install requests pandas pytz
chmod +x integrador.sh
```

## 5. Atualizar código (Git — recomendado)

**No PC:** commit + push em `main` (**sem** `.config`).

**No VPS:**

```bash
cd /home/gogotech/integracao/sstrevo
git pull origin main
source .venv/bin/activate
pip install requests pandas pytz   # se houver dependência nova
```

O `.config` de produção **não** é sobrescrito pelo `git pull`.

## 6. Testes

```bash
cd /home/gogotech/integracao/sstrevo
source .venv/bin/activate

# Só CSV (sem enviar ao Hevi)
python funcionarios.py csv
python afastamentos.py csv
python demissoes.py csv

# Integração completa (envia ao Hevi)
./integrador.sh
# ou: python main.py
```

## 7. Cron (Linux)

```bash
cd /home/gogotech/integracao/sstrevo
chmod +x integrador.sh
crontab -e
```

Exemplo — a cada 30 minutos (mesmo padrão das outras integrações):

```cron
*/30 * * * * cd /home/gogotech/integracao/sstrevo && flock -n /tmp/integrador_sstrevo.lock ./integrador.sh >> /home/gogotech/integracao/sstrevo/integrador.log 2>&1
```

Conferir:

```bash
crontab -l
tail -f /home/gogotech/integracao/sstrevo/integrador.log
```

## 8. Checklist pós-deploy

```bash
cd /home/gogotech/integracao/sstrevo
test -f .config && echo "OK .config" || echo "FALTA .config"
test -x integrador.sh && echo "OK integrador.sh" || chmod +x integrador.sh
source .venv/bin/activate
python -c "import requests, pandas, pytz; print('OK deps')"
./integrador.sh
```

## 9. Rede / firewall

Saída **HTTPS (443)** para:

- Contabit (`dalloglio.contabit.com.br`)
- Hevi (`stou.ifractal.com.br`)

Não é necessário abrir porta de entrada se o script só faz conexões de saída.

## 10. Rollback

Restaurar o backup da pasta (principalmente `.config`) e, se preciso:

```bash
cd /home/gogotech/integracao/sstrevo
git log --oneline -5
git checkout <commit_anterior> -- .
```

---

*Integração sstrevo — Contabit → Hevi — caminho: `/home/gogotech/integracao/sstrevo`*
