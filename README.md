# Odoo XML-RPC CSV Importer

Script em Python para importação de contatos no Odoo a partir de arquivos CSV, utilizando a API XML-RPC oficial.
O foco é **automação, controle de duplicidade e eficiência operacional** em cenários empresariais.

## Visão geral

Este script lê um arquivo CSV estruturado, valida os dados, elimina duplicidades e cria registros de contatos (`res.partner`) diretamente no Odoo.
Foi desenvolvido para substituir processos manuais ou importações inconsistentes, reduzindo tempo de carga e erros operacionais.

Principais objetivos:

* Automatizar a criação de contatos no Odoo
* Evitar duplicidades no CSV e no banco de dados
* Resolver corretamente países e estados
* Melhorar performance por meio de cache em memória

## Funcionalidades

* Autenticação no Odoo via XML-RPC
* Leitura de CSV com validação de campos obrigatórios
* Eliminação de registros duplicados no próprio CSV (nome e e-mail)
* Verificação de contatos já existentes no Odoo
* Criação de contatos no modelo `res.partner`
* Resolução automática de `country_id` e `state_id`
* Cache em memória para países e estados, reduzindo chamadas repetidas à API
* Log de execução e tempo total do processo

## Estrutura esperada do CSV

O script utiliza `csv.DictReader` e espera as seguintes colunas:

* Nome completo
* E-mail
* Cargo
* Nome da empresa
* Cidade
* País
* Estado
* Localização
* LinkedIn

Registros sem **nome** ou **e-mail** são considerados inválidos e ignorados.

## Requisitos

* Python 3.9+
* Odoo com XML-RPC habilitado
* Acesso válido ao banco do Odoo

Dependências:

* python-dotenv

## Configuração

Crie um arquivo `.env` na raiz do projeto com as credenciais do Odoo:

```
ODOO_URL=https://seu-odoo.com
ODOO_DB=nome_do_banco
ODOO_USERNAME=usuario
ODOO_PASSWORD=senha
```

O arquivo CSV deve estar no mesmo diretório do script (por padrão: `test.csv`).

## Execução

```bash
python app.py
```

Ao final da execução, o script exibe:

* Total de contatos processados
* Contatos criados
* Contatos ignorados por duplicidade
* Tempo total de execução

## Arquitetura e decisões técnicas

* **XML-RPC**: utilizado por compatibilidade direta com o Odoo, sem dependência de módulos extras.
* **Cache de países e estados**: evita múltiplas consultas repetidas ao Odoo, melhorando significativamente a performance em cargas grandes.
* **Validação antecipada**: duplicidades são filtradas antes de qualquer chamada ao Odoo.
* **Separação de responsabilidades**: autenticação, leitura de CSV, verificação de existência e criação de contatos são funções independentes.

## Limitações conhecidas

* Não realiza atualização de contatos existentes, apenas criação.
* Estrutura do CSV é fixa.
* Não há paralelismo; a execução é sequencial.

Essas limitações são intencionais para manter previsibilidade e segurança na carga de dados.

## Caso de uso típico

* Importação de leads comerciais
* Migração inicial de contatos
* Integração pontual com sistemas externos que exportam CSV
* Padronização de bases de contatos no Odoo

## Licença

Uso livre para fins educacionais ou internos.
Avaliar adaptações antes de uso em ambientes produtivos de grande escala.