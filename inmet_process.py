import argparse
import logging
import os
import re
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import unidecode

#Configurando o sistema de logging para exibir progresso
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#Funções de processamento (Parte 1)
def download_inmet_zip(year: str) -> zipfile.ZipFile | None:
    """Baixa e abre o arquivo ZIP do INMET para um ano."""
    url = f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
    logging.info(f"Baixando dados para o ano {year} de {url}")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        zip_file = zipfile.ZipFile(io.BytesIO(response.content))
        logging.info(f"Download do ano {year} concluído com sucesso.")
        return zip_file
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha no download para o ano {year}. Erro: {e}")
        return None

def process_station_csv(csv_file_info: zipfile.ZipInfo, zip_file: zipfile.ZipFile, output_root: str, year: str):
    """Lê um único CSV de estação, processa os dados e salva os arquivos de saída."""
    #Extraindo o código da estação do nome do arquivo
    station_code_match = re.search(r'INMET_.*_([A-Z]\d{3})_.*', csv_file_info.filename)
    if not station_code_match:
        return
    station_code = station_code_match.group(1)

    try:
        with zip_file.open(csv_file_info) as file:
            df = pd.read_csv(file, sep=';', encoding='latin1', decimal=',', skiprows=8, dtype=str)

        #Normalizando os nomes das colunas
        df.columns = [unidecode.unidecode(col).strip().lower() for col in df.columns]

        #Criando a coluna 'datetime' e definindo índice
        df['datetime'] = pd.to_datetime(df['data'] + ' ' + df['hora utc'], format='%Y/%m/%d %H%M UTC', errors='coerce')
        df.dropna(subset=['datetime'], inplace=True)
        df.drop_duplicates(subset=['datetime'], keep='first', inplace=True)
        df.set_index('datetime', inplace=True)

        #Buscando e processamdo a coluna de precipitação
        prec_col = next((col for col in df.columns if 'precipitacao total' in col), None)
        if prec_col:
            var_df = df[[prec_col]].copy()
            var_df.rename(columns={prec_col: 'value'}, inplace=True)
            var_df['value'] = pd.to_numeric(var_df['value'], errors='coerce')
            var_df.dropna(subset=['value'], inplace=True)
            output_path = os.path.join(output_root, 'inmet_stations', 'processed', 'total_precipitation', str(year))
            os.makedirs(output_path, exist_ok=True)
            output_file = os.path.join(output_path, f"{station_code}.csv")
            var_df.to_csv(output_file)

        #Buscando e processando a coluna de temperatura
        temp_col = next((col for col in df.columns if 'bulbo seco' in col), None)
        if temp_col:
            var_df = df[[temp_col]].copy()
            var_df.rename(columns={temp_col: 'value'}, inplace=True)
            var_df['value'] = pd.to_numeric(var_df['value'], errors='coerce')
            var_df.dropna(subset=['value'], inplace=True)
            output_path = os.path.join(output_root, 'inmet_stations', 'processed', '2m_air_temperature', str(year))
            os.makedirs(output_path, exist_ok=True)
            output_file = os.path.join(output_path, f"{station_code}.csv")
            var_df.to_csv(output_file)

        logging.info(f"Estação {station_code} processada com sucesso.")
    except Exception as e:
        logging.warning(f"Erro ao processar a estação {station_code} do arquivo {csv_file_info.filename}: {e}")

#Funções de relatório (Parte 2)
def calculate_completeness(file_path: str) -> dict:
    """Calcula o percentual de completude dos dados para uma estação."""
    station_code = os.path.basename(file_path).replace('.csv', '')
    try:
        df = pd.read_csv(file_path)
        if df.empty:
            return {'station_code': station_code, 'completeness': 0.00}

        df['datetime'] = pd.to_datetime(df['datetime'])
        start_dt, end_dt = df['datetime'].min(), df['datetime'].max()
        valid_records = pd.to_numeric(df['value'], errors='coerce').notna().sum()
        expected_records = int((end_dt - start_dt).total_seconds() / 3600) + 1

        if expected_records <= 0:
            return {'station_code': station_code, 'completeness': 0.00}

        completeness = round(valid_records/expected_records, 2)
        return {'station_code': station_code, 'completeness': completeness}
    except Exception:
        return {'station_code': station_code, 'completeness': 0.00}

def generate_completeness_report(year: str, output_root: str):
    """Gera o relatório de completude."""
    logging.info(f"Iniciando geração de relatórios de completude para {year}.")
    variables = ['total_precipitation', '2m_air_temperature']
    for var in variables:
        processed_dir = os.path.join(output_root, 'inmet_stations', 'processed', var, str(year))
        if not os.path.isdir(processed_dir):
            logging.warning(f"Diretório de dados processados não encontrado para {var}/{year}. Pulando relatório.")
            continue

        station_files = [os.path.join(processed_dir, f) for f in os.listdir(processed_dir) if f.endswith('.csv')]

        with ThreadPoolExecutor(max_workers=4) as executor:
            report_data = list(executor.map(calculate_completeness, station_files))

        if report_data:
            report_df = pd.DataFrame(report_data)
            report_output_path = os.path.join(output_root, f"{var}_{year}_completeness.csv")
            report_df.to_csv(report_output_path, sep=';', index=False)
            logging.info(f"Relatório de completude gerado em: {report_output_path}")

#Gerenciamento do pipeline
def process_year_data(year, output_root):
    """Gerencia o download e o processamento paralelo dos dados."""
    zip_file = download_inmet_zip(year)
    if not zip_file:
        return
    csv_files = [f for f in zip_file.infolist() if f.filename.lower().endswith('.csv')]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_station_csv, csv_info, zip_file, output_root, year) for csv_info in csv_files]
        for future in futures:
            future.result()

def main():
    parser = argparse.ArgumentParser(description="Processador de dados meteorológicos do INMET.")
    parser.add_argument('--years', required=True, nargs='+', help='Um ou mais anos para processar.')
    parser.add_argument('--out-root', required=True, help='Diretório raiz para salvar os arquivos de saída.')

    args = parser.parse_args()

    logging.info(f"Anos a processar: {args.years}")
    logging.info(f"Diretório de saída: {args.out_root}")

    #Loop para executar o pipeline para cada ano solicitado
    for year in args.years:
        logging.info(f"--- Iniciando processamento para o ano de {year} ---")
        process_year_data(year, args.out_root)
        generate_completeness_report(year, args.out_root)
        logging.info(f"--- Finalizado processamento para o ano de {year} ---")

if __name__ == "__main__":
    main()