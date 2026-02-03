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
## Execução — Teste 1 (Integração com API Pública)

Para executar o Teste 1 completo (1.1 → 1.3):    
```bash
python main_test_1.py
```
---
### O que o Teste 1 faz

#### 1.1 — Download dos dados

- Acessa o diretório público da ANS (Demonstrações Contábeis)
- Identifica automaticamente os últimos 3 trimestres disponíveis
- Baixa os arquivos ZIP e extrai seu conteúdo

#### 1.2 — Normalização / padronização (MVP)

- Localiza automaticamente os CSVs trimestrais extraídos
- (Nesta versão, a normalização intermediária está em formato MVP, preparando os dados para a consolidação)

#### 1.3 — Consolidação e inconsistências

- Consolida os dados dos 3 trimestres em um único CSV com as colunas:
- CNPJ, RazaoSocial, Trimestre, Ano, ValorDespesas
- Gera auditoria de inconsistências (valores, datas, mapeamento CADOP)
- Compacta o CSV final em um arquivo ZIP
---

### Saída final exigida

O arquivo solicitado no enunciado é gerado automaticamente em:
```bash
output/teste_1/consolidado_despesas.zip
```
---

### Trade-offs técnicos

- Foi adotado processamento incremental (chunks) para reduzir uso de memória e permitir o processamento de arquivos grandes.
- Dados e arquivos intermediários são gerados automaticamente durante a execução.
---
### Observação sobre arquivos gerados

As pastas data/ e output/ são criadas automaticamente durante a execução do projeto e não são versionadas no GitHub (ver .gitignore).