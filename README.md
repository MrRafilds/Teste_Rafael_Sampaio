# TESTE DE ENTRADA PARA ESTAGIÁRIOS v2.0
Intuitive Care - Healthtech de SaaS Vertical

Este repositório contém minha solução para o processo seletivo técnico da Intuitive Care.

---

## Requisitos
- Python 3.10+ (ou 3.11)
- pip

---

## Instalação

Na raiz do projeto, instale as dependências:
```bash
pip install -r requirements.txt
```

---

## Execução do Projeto

O projeto possui **um único ponto de entrada** (`main.py`).

A execução abaixo realiza **todo o pipeline**, incluindo:
- Teste 1 (Integração com API Pública – etapas 1.1 a 1.3)
- Teste 2 (Validação, Enriquecimento e Agregação – etapas 2.1 a 2.3)

```bash
python main.py
```
---

## O que o Teste 1 faz?

### 1.1 — Download dos dados
- Acessa o diretório público da ANS (Demonstrações Contábeis)
- Identifica automaticamente os últimos 3 trimestres disponíveis
- Baixa os arquivos ZIP e extrai seu conteúdo

### 1.2 — Normalização / Padronização (MVP)
- Localiza automaticamente os CSVs trimestrais extraídos
- Nesta versão, a normalização intermediária é tratada como MVP, preparando os dados para a consolidação

### 1.3 — Consolidação e Tratamento de Inconsistências
- Consolida os dados dos 3 trimestres em um único CSV com as colunas:
  - CNPJ
  - RazaoSocial
  - Trimestre
  - Ano
  - ValorDespesas
- Gera auditoria de inconsistências (valores, datas e mapeamento CADOP)
- Compacta o CSV final em um arquivo ZIP

---

## Saída final do Teste 1
```bash
output/teste_1/consolidado_despesas.zip
```

---

## Trade-offs técnicos — Teste 1
- Processamento incremental (chunks) para reduzir uso de memória
- Arquivos intermediários são gerados automaticamente durante a execução

---

## Observação sobre arquivos gerados
As pastas `data/` e `output/` são criadas automaticamente durante a execução do projeto e não são versionadas no GitHub (ver `.gitignore`).

---

## Execução — Teste 2 (Validação, Enriquecimento e Agregação)

O Teste 2 utiliza como entrada o CSV consolidado gerado no Teste 1.3 e executa três etapas sequenciais:
- Validação dos dados
- Enriquecimento com dados cadastrais
- Agregação e análise estatística

A execução completa do Teste 2 ocorre automaticamente após o Teste 1:
```bash
python main.py
```

---

## O que o Teste 2 faz?

### 2.1 — Validação de Dados

**CNPJ:**
- Aceita com ou sem máscara
- Normaliza para 14 dígitos
- Valida dígitos verificadores (DV)

**ValorDespesas:**
- Deve ser numérico
- Deve ser positivo (> 0)

**RazaoSocial:**
- Não pode ser vazia

**Estratégia para CNPJs inválidos (Trade-off técnico):**
- Estratégia adotada: `QUARANTINE`
- Registros inválidos não entram no dataset válido
- Preservados em arquivo separado com o motivo

**Arquivos gerados:**
- `validated/valid_rows.csv`
- `validated/invalid_rows.csv`
- `validated/summary.json`
- `README_validacao.md`

---

### 2.2 — Enriquecimento de Dados

- Fonte: Cadastro de Operadoras Ativas da ANS (CADOP)
- Chave de junção: CNPJ
- Tipo de join: `LEFT JOIN`

**Colunas adicionadas:**
- RegistroANS
- Modalidade
- UF
- CadastroStatus

**Tratamento de inconsistências:**
- Registros sem match: mantidos e marcados como `SEM_MATCH_CADOP`
- CNPJs duplicados: resolvidos por regra determinística
- Relatórios gerados:
  - `issues/issues_sem_match_cadastro.csv`
  - `issues/issues_cadastro_duplicado.csv`
  - `README_enriquecimento.md`

---

### 2.3 — Agregação e Análise Estatística

**Agrupamento por:**
- RazaoSocial
- UF

**Cálculos:**
- Total de despesas
- Média trimestral
- Desvio padrão

**Ordenação:**
- Decrescente por `ValorTotalDespesas`

---

## Saída final do Teste 2
```bash
output/teste_2/
```

**Arquivo final exigido:**
```bash
Teste_Rafael_Sampaio.zip
```

**Conteúdo:**
- `despesas_agregadas.csv`

---

## Estrutura do Projeto
```text
Teste_Rafael_Sampaio/
├── api/
│   └── ans_client.py
├── processing/
│   ├── consolidate_1_3.py
│   ├── validate_2_1.py
│   ├── enrich_2_2.py
│   └── aggregate_2_3.py
├── data/            # gerado automaticamente (não versionado)
├── output/          # gerado automaticamente (não versionado)
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Observações Finais
- O projeto prioriza clareza, rastreabilidade e qualidade do código
- As decisões técnicas foram tomadas conscientemente
- O escopo foi limitado intencionalmente, priorizando consistência e documentação

**Autor:** Rafael Bento Tieghi Sampaio  
**Período de desenvolvimento:** 28/01 a 04/02
