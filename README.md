# Odoo ETL Engine

![Odoo XML-RPC](https://img.shields.io/badge/Odoo-XML--RPC-7A7A7A.svg?style=for-the-badge)
![alt text](https://img.shields.io/badge/Python-3.13-14354C?style=for-the-badge&logo=python&logoColor=white)
![alt text](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![alt text](https://img.shields.io/badge/uv-Fast_Packager-magenta?style=for-the-badge)

Engine de ingestão de dados de alta performance projetada para integrar grandes volumes de contatos (`res.partner`) no ERP Odoo via XML-RPC. 

Diferente de scripts sequenciais comuns, esta aplicação foi arquitetada sob pricipios de Clean **Architecture** para maximizar o throughput de I/O de rede através de **execução concorrente** thread-safe, mitigação de gargalos nativos do Odoo, governança estrita de dados na entrada, observabilidade em tempo real e garantindo **zero perda de dados** através de estratégias de resiliência (DLQ e Exponential Backoff).

## Arquitetura & Otimizações de Performance

Este projeto resolve os problemas clássicos de importação de dados no Odoo:

* **Concorrência I/O Bound:** Utilização de `ThreadPoolExecutor` com controle de `Futures` para paralelizar as requisições HTTP (XML-RPC). Como o gargalo é a rede e o banco de destino, as threads do CPython operam com eficiência contornando o GIL.
* **Thread-Safety:** Garante captura de exceções em tempo real. Contadores de métricas (`ImportStats`) e gravações em disco são blindados com `threading.Lock()` para evitar Race Conditions.
* **Governança & Type-Safety:** Validação determinística na borda (Domain Layer) utilizando **Pydantic**. Dados malformados ou incompletos são expurgados do pipeline antes de consumirem recursos de rede ou memória.
* **Mitigação de Queries N+1 (Bulk Search):** Em vez de validar se um e-mail existe linha a linha, o script extrai um `Set` de e-mails do lote atual e faz um único `search_read` remoto no Odoo, reduzindo o tráfego de rede drasticamente.
* **Gerenciamento de Memória (Streaming):** O arquivo CSV nunca é carregado inteiro na RAM. O uso de `Generators` (`yield`) e a função `chunker` garantem uma pegada de memória constante, independentemente se o arquivo tem 10 mil ou 1 milhão de linhas.
* **Cache em Memória Thread-Safe:** Entidades de domínio lentas (Países e Estados) sofrem Warm-up no boot da aplicação, substituindo milhares de requisições XML-RPC por consultas locais em memória na velocidade do processador.
* **Resiliência Estrutural (DLQ):** Padrão Fail-Fast e blindado contra falhas de rede transientes, tratadas via *Exponential Backoff*. Falhas críticas (ex: dados corrompidos) não param o pipeline; o registro é isolado de forma assíncrona e *thread-safe* em um arquivo de **Dead Letter Queue** em formato **JSONL** para auditoria posterior.
* **Observabilidade:** Logs estruturados assíncronos e painel de telemetria em tempo real via CLI, expondo throughput, workers ativos e volume de rejeição.

## Stack Tecnológico

* **Linguagem:** Python 3.13
* **Arquitetura:** Clean Architecture, Dependency Injection, Interfaces (Protocol)
* **Package Manager:** [uv](https://github.com/astral-sh/uv) (Ultra-rápido, resolvendo dependências em milissegundos)
* **CLI:** `structlog`, `Typer`, `Rich`
* **Resiliência:** `Tenacity` (Retry/Backoff)
* **Infraestrutura:** Docker & Docker Compose (PostgreSQL 15 + Odoo)

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
docker compose run --rm etl data/test.csv --max-workers 3 --batch-size 1000
```

## Execução Local (Desenvolvimento)

Caso prefira rodar localmente usando o gerenciador `uv`:

```bash
# Sincroniza as dependências via uv
uv sync --frozen

# Executa o CLI do projeto
uv run etl data/test.csv --max-workers 3 --batch-size 1000
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

Registros sem `name` ou `email` são ignorados diretamente no stream (`CsvManager`), não consumindo I/O.

## Governança de Falhas: A Dead Letter Queue (JSONL)

Em ambientes de dados distribuídos, descartar dados sem rastro é inaceitável. O sistema implementa uma DLQ formatada em **JSON Lines (NDJSON)**, padrão ideal para ingestão futura por *Crawlers* de Data Lakes (ex: AWS Glue / Athena).

O sistema isola categoricamente:
* `validation_error`: Erros intrínsecos ao dado (Schema Pydantic violado, ex: e-mail sem `@`).
* `batch_processing_error`: Erros de I/O ou instabilidade do Odoo (inclui *Stacktrace* e *Exception Type*).

Se um lote inteiro falhar mesmo após as tentativas de *Retry Exponencial* (ex: Odoo fora do ar prolongadamente), os registros desse lote são salvos no arquivo `failed_records.jsonl` na raiz da execução, com detalhes do payload e detalhes dos erros encontrados.

As falhas são gravadas de forma assíncrona e *thread-safe*, garantindo que a esteira principal nunca sofra *lock* de disco prolongado.

## Telemetria (CLI)

O painel fornece dados auditáveis no final de cada execução:

```text
╭──────────────────────────────────────────────────────────╮
│   File                          data\100000.csv          │
│   Threads                       3                        │
│   Processed Batches             100                      │
│   Batch Size                    1000                     │
│   Created Contacts              87,975                   │
│   Created Contacts Rate         2447.01/s                │
│   Processed Contacts Rate       2781.49/s                │
│   Duplicated Contacts in CSV    9,999                    │
│   Validation Errors             0                        │
│   Total Time                    35.95 s                  │
╰──────────────────────────────────────────────────────────╯
```