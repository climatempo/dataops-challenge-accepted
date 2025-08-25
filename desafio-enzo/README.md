# Desafio Técnico - Climatempo

Este repositório contém a solução para o **Desafio Técnico de DataOps da Climatempo**.  
O objetivo é baixar, processar e calcular a completude de séries históricas de estações meteorológicas do INMET.

---

## Dependências

As bibliotecas necessárias estão listadas em `requirements.txt`.

Instale com:

```bash
pip install -r requirements.txt
```
---

## Como executar

O script principal é `primeiro_codigo.py`.

Exemplo de execução:

python primeiro_codigo.py --years 2024 2025 --out-root ./data

### Parâmetros disponíveis
- `--years` : anos a processar (ex: `2024 2025`)
- `--out-root` : diretório raiz de saída (onde os arquivos vão estar)
- `--station-filter` : lista de códigos de estação selecionados, precisam estar separados por vírgula (opcional)
- `--workers` : número de workers (paralelismo, ainda não implementado)

---

## Estrutura de saída

Após a execução, os dados serão organizados em:

### Dados processados
```
./data/inmet_stations/processed/total_precipitation/2025/A701.csv
./data/inmet_stations/processed/2m_air_temperature/2025/A701.csv
```

### Relatórios de completude por estação
```
./data/total_precipitation_2025.csv
./data/2m_air_temperature_2025.csv
```

---

## Exemplo prático

Processar o ano de 2025 para duas estações específicas:

python desafio.py --years 2025 --out-root ./data --station-filter A701,A354

Isso irá:
- Baixar o ZIP de 2025 do portal do INMET
- Extrair e processar apenas as estações `A701` e `A354`
- Gerar os CSVs normalizados
- Criar o relatório de completude para 2025 nas duas variaveis

---

## Tecnologias utilizadas
- Python 3.9+
- pandas
- requests
- unidecode
