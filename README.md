# Odoo ETL Engine

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg) ![uv](https://img.shields.io/badge/package_manager-uv-magenta.svg) ![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg) ![Odoo XML-RPC](https://img.shields.io/badge/Odoo-XML--RPC-7A7A7A.svg)

Engine de ingestão de dados em lote projetada para integrar grandes volumes de contatos (`res.partner`) no ERP Odoo via XML-RPC. 

Diferente de scripts sequenciais comuns, esta aplicação foi arquitetada para maximizar o throughput de I/O de rede através de **execução concorrente**, mitigando gargalos nativos do Odoo (N+1 queries) e garantindo **zero perda de dados** através de estratégias de resiliência (DLQ e Exponential Backoff).

## Arquitetura & Otimizações de Performance

Este projeto resolve os problemas clássicos de importação de dados no Odoo:

* **Concorrência I/O Bound:** Utilização de `ThreadPoolExecutor` para paralelizar as requisições HTTP (XML-RPC). Como o gargalo é a rede e o banco de destino, as threads do CPython operam com eficiência contornando o GIL.
* **Mitigação de Queries N+1 (Bulk Search):** Em vez de validar se um e-mail existe linha a linha, o script extrai um `Set` de e-mails do lote atual e faz um único `search_read` remoto no Odoo, reduzindo o tráfego de rede drasticamente.
* **Gerenciamento de Memória (Streaming):** O arquivo CSV nunca é carregado inteiro na RAM. O uso de `Generators` (`yield`) e a função `chunker` garantem uma pegada de memória constante, independentemente se o arquivo tem 10 mil ou 1 milhão de linhas.
* **Cache em Memória Thread-Safe:** Consultas repetitivas a chaves estrangeiras (`res.country` e `res.country.state`) são cacheadas em memória durante a execução do lote.
* **Resiliência e Recuperação (DLQ):** Falhas de rede transientes são tratadas via *Exponential Backoff* (`Tenacity`). Falhas críticas (ex: dados corrompidos) não param o pipeline; o registro é isolado de forma assíncrona e *thread-safe* em um arquivo de **Dead Letter Queue (DLQ)** para auditoria posterior.

## Stack Tecnológico

* **Linguagem:** Python 3.13
* **Package Manager:** [uv](https://github.com/astral-sh/uv) (Ultra-rápido, resolvendo dependências em milissegundos)
* **CLI:** `Typer`
* **Resiliência:** `Tenacity` (Retry/Backoff)
* **Infraestrutura:** Docker & Docker Compose (PostgreSQL 15 + Odoo 16)

## Configuração do Ambiente

1. Clone o repositório:
```bash
git clone https://github.com/antonyharo/odoo-xmlrpc-csv-importer.git
cd odoo-xmlrpc-csv-importer
```

2. Crie o arquivo de configuração a partir do exemplo:
```bash
cp .env.example .env
```
*Preencha com as credenciais do seu Odoo alvo ou mantenha o padrão para rodar no container local.*

3. Adicione seu arquivo `.csv` de contatos no diretório `data/` (ex: `data/contacts.csv`).

## Execução via Docker (Recomendado)

O projeto inclui um `docker-compose.yaml` completo que sobe o banco de dados (Postgres), a aplicação Odoo e encapsula o script ETL num *Profile* isolado.

**1. Suba a infraestrutura do Odoo:**
```bash
docker compose up -d db odoo
```
*Aguarde alguns segundos. O container possui um `healthcheck` garantindo que o Odoo e o Postgres estejam prontos para receber requisições.*

**2. Execute o Job ETL:**
Como o serviço do ETL está configurado com `profiles: ["cli"]`, ele não roda como um daemon, mas como um executor efêmero. 
```bash
docker compose run --rm etl data/test.csv --max-workers 4 --batch-size 1000
```

## Execução Local (Desenvolvimento)

Caso prefira rodar localmente usando o gerenciador `uv`:

```bash
# Sincroniza as dependências via uv
uv sync --frozen

# Executa o CLI do projeto
uv run etl data/test.csv --max-workers 4 --batch-size 1000
```

## Documentação do CLI (Typer)

A aplicação fornece uma interface de linha de comando robusta:

```
Usage: etl [OPTIONS] FILE_NAME

Arguments:
  FILE_NAME      Caminho do arquivo .CSV a ser importado. [obrigatório]

Options:
  --batch-size INTEGER   Total de contatos por lote a serem processados. [default: 1000]
  --max-workers INTEGER  Total de threads simultâneas para chamadas I/O. [default: 4]
  --help                 Exibe esta mensagem e sai.
```

### Cuidados com a Escala (`max-workers`)
O Odoo utiliza Gunicorn/WSGI processando requisições de forma síncrona. Um número excessivo de `max-workers` (ex: `> 10`) não aumentará a velocidade local; em vez disso, esgotará o pool de conexões do PostgreSQL no servidor Odoo (`Connection Refused`). Recomendamos manter entre **2 e 5 workers**, ajustando o `batch-size` conforme a capacidade de memória do servidor destino.

## Estrutura do CSV

O sistema processa colunas nativas do modelo `res.partner`. Os campos mínimos para ingestão são:
- `name` (Obrigatório)
- `email` (Obrigatório, usado como chave de idempotência e deduplicação)
- `country_id` (Nome do país, resolvido automaticamente pelo cache)
- `state_id` (Nome do estado, resolvido automaticamente pelo cache)

Registros sem `name` ou `email` são ignorados diretamente no stream (`CsvManager`), não consumindo I/O.

## Tratamento de Erros e DLQ

Se um lote inteiro falhar mesmo após as tentativas de *Retry Exponencial* (ex: Odoo fora do ar prolongadamente), os registros desse lote são salvos no arquivo `failed_records.csv` na raiz da execução, com uma coluna adicional `error_log` contendo o erro encontrado.

A escrita no DLQ é protegida por `threading.Lock()` para prevenir corrupção de arquivo (*Race Conditions*) quando múltiplas threads falham simultaneamente.