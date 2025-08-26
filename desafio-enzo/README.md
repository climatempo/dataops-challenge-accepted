# Desafio Técnico - Climatempo

Este repositório contém a solução desenvolvida para o desafio técnico da Climatempo.

## Funcionalidades Implementadas

- Download automático dos dados históricos do INMET (arquivos ZIP por ano).
- Extração dos arquivos CSV do ZIP baixado.
- Processamento dos arquivos de estação, com:
  - Normalização das colunas.
  - Conversão de datas e horas para formato `datetime`.
  - Extração das variáveis:
    - Precipitação horária.
    - Temperatura do ar (bulbo seco).
  - Remoção de valores inválidos (-9999).
  - Geração de arquivos CSV processados, organizados por variável e ano.
- Cálculo da **completude** (percentual de registros válidos em relação ao esperado).
- Suporte a múltiplos anos e múltiplas estações.
  - É possível processar várias estações em paralelo, acelerando a execução.
  - O parâmetro `--workers` define o número de processos em paralelo.
  - Exemplo: `--workers 4` utiliza até 4 processos simultâneos.

## Como executar

### Requisitos
- Python 3.8+
- Instalar dependências:
  ```bash
  pip install -r requirements.txt
  ```

### Uso

Rodar o script principal:
```bash
python desafio.py --years 2024 2025 --out-root ./data --workers 4
```

Parâmetros:
- `--years` → anos a serem processados (um ou mais).
- `--out-root` → diretório onde salvar os arquivos processados.
- `--workers` → número de processos em paralelo (default = 1, ou seja, sequencial).
- `--station-filter` → (opcional) lista de códigos de estações, separadas por vírgula.

### Exemplos

1. Processar um único ano de forma sequencial:
```bash
python desafio.py --years 2024 --out-root ./data
```

2. Processar dois anos com paralelismo (4 processos):
```bash
python desafio.py --years 2023 2024 --out-root ./data --workers 4
```

3. Processar apenas uma estação específica:
```bash
python desafio.py --years 2024 --out-root ./data --station-filter A301
```

## Estrutura de Saída

```
out-root/
 └── inmet_stations/
     └── processed/
         ├── total_precipitation/
         │   └── 2024/
         │       └── A301.csv
         └── 2m_air_temperature/
             └── 2024/
                 └── A301.csv
 └── total_precipitation_2024.csv
 └── 2m_air_temperature_2024.csv
```

## Relatórios de Completude

Para cada variável e ano, é gerado um arquivo CSV contendo o código da estação e o percentual de completude dos dados.

Exemplo (`total_precipitation_2024.csv`):
```
station_code;completeness
A301;0.98
A354;0.75
```

---
📌 Desenvolvido por Enzo Gaddo para o processo seletivo Climatempo.
