# -*- coding: utf-8 -*-
"""
Created on Thu Aug 21 16:57:17 2025

@author: Enzo
"""

import argparse
import os
import logging
import requests
from requests.adapters import HTTPAdapter, Retry
import re
import pandas as pd
from unidecode import unidecode
import zipfile


def download_zip(year: int, out_dir: str):
    """Baixa o arquivo ZIP do INMET para o ano informado."""
    '''
   Args:
       year (int): Ano desejado (ex: 2025).
       out_dir (str): Diretório onde salvar o arquivo.
       
   Returns:
       str: Caminho do arquivo ZIP baixado.
   '''
    url = f'https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip'
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"{year}.zip")

    if os.path.exists(zip_path):
       print(f"[INFO] Arquivo {zip_path} já existe, pulando download.")
       return zip_path

    print(f"[INFO] Baixando {url} ...")

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    response = session.get(url, stream=True, timeout=60)
    response.raise_for_status()
    
    
    with open(zip_path, "wb") as f:
       for chunk in response.iter_content(chunk_size=1024*1024):
           if chunk:
               f.write(chunk)

    print(f"[INFO] Download concluído: {zip_path}")
    return zip_path

def extract_zip(zip_path: str, extract_to: str):
    """Extrai os arquivos de um ZIP para um diretório."""
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    
        zip_ref.extractall(extract_to)
    
    print(f"[INFO] Arquivos extraídos para: {extract_to}")

def parse_station_code(filename: str) -> str:
    """Extrai o código da estação a partir do nome do arquivo CSV."""
    """
  Extrai o código da estação (ex: A354) a partir do nome do arquivo CSV do INMET.

  Args:
      filename (str): Nome do arquivo (com ou sem caminho).
  
  Returns:
      str: Código da estação (ex: A354) ou None se não encontrado.
  """
    base = os.path.basename(filename)

    match = re.search(r"([A-Z]\d{3})", base)
    if match:
        return match.group(1)

    print(f"[WARN] Não foi possível extrair código da estação de: {base}")
    return None

def normalize_column(col: str) -> str:
    """Normaliza nomes de colunas: minúsculas, sem acentos, sem espaços extras."""
    
    return unidecode(col.strip().lower().replace(" ", "_"))

def process_station_file(csv_path: str, out_root: str, year: int):
    
    """
   Processa um arquivo bruto do INMET e gera CSVs de precipitação e temperatura.

   Args:
       csv_path (str): Caminho do CSV da estação (dentro do ZIP ou extraído).
       out_root (str): Diretório raiz de saída.
       year (int): Ano do dado.
   """
    station_code = parse_station_code(csv_path)
    if not station_code:
        print(f"[WARN] Código da estação não encontrado em {csv_path}")
        return

    print(f"[INFO] Processando estação {station_code} ({year})")
    
    df = pd.read_csv(
        csv_path,
        sep=";",
        encoding="latin1",
        decimal=",",
        dtype=str,
        skiprows=8,
        on_bad_lines="skip"
    )
    
    df.columns = [normalize_column(c) for c in df.columns]
    df["hora"] = (df["hora_utc"].astype(str).str.zfill(4)).str[:2]  # pega só HH
    df["tempo"] = df["data"].str.strip() + " " + df["hora"]
    df["datetime"] = pd.to_datetime(df["tempo"], format="%Y/%m/%d %H", errors="coerce")
    df = df.dropna(subset=["datetime"])
    df.drop(columns=["data", "hora_utc", "hora", "tempo"],inplace=True)

    vars_map = {}

    for col in df.columns:
        if "precipitacao_total" in col:
            vars_map[col] = "total_precipitation"
        elif "temperatura" in col and "seco" in col:
            vars_map[col] = "2m_air_temperature"

    for col, varname in vars_map.items():

        tmp = df[["datetime", col]].copy()
        tmp.columns = ["datetime", "value"]
        tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
        tmp = tmp.dropna(subset=["value"])
        tmp = tmp.loc[~tmp["value"].isin([-9999])]
        tmp = tmp.drop_duplicates(subset=["datetime"], keep="first")
        out_dir = os.path.join(out_root, "inmet_stations", "processed", varname, str(year))
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"{station_code}.csv")
        tmp.to_csv(out_file, index=False)
        print(f"[INFO] Gerado: {out_file}")

def compute_completeness_for_year(year: int, out_root: str, variable: str):
    """
    Calcula a completude dos dados processados para todas as estações de um ano.

    Args:
        year (int): Ano dos dados.
        out_root (str): Diretório raiz de saída.
        variable (str): Variável a processar ("total_precipitation" ou "2m_air_temperature").
    """
    print(f"[INFO] Calculando completude para {variable} ({year})...")
    
    base_dir = os.path.join(out_root, "inmet_stations", "processed", variable, str(year))
    if not os.path.exists(base_dir):
        print(f"[WARN] Diretório não encontrado: {base_dir}")
        return

    results = []
    
    for fname in os.listdir(base_dir):
        if not fname.endswith(".csv"):
            continue

        station_code = os.path.splitext(fname)[0]
        file_path = os.path.join(base_dir, fname)
        
        try:
            df = pd.read_csv(file_path, parse_dates=["datetime"])
        except Exception as e:
            print(f"[ERRO] Falha ao ler {file_path}: {e}")
            results.append((station_code, 0.0))
            continue

        if df.empty:
            results.append((station_code, 0.0))
            continue
        
        start_dt = df["datetime"].min()
        end_dt = df["datetime"].max()

        expected_records = int((end_dt - start_dt).total_seconds() / 3600) + 1
        valid_records = df["value"].notna().sum()

        if expected_records <= 0:
            completeness = 0.0
        else:
            completeness = round(valid_records / expected_records, 2)

        results.append((station_code, completeness))

    out_df = pd.DataFrame(results, columns=["station_code", "completeness"])

    out_file = os.path.join(out_root, f"{variable}_{year}.csv")
    out_df.to_csv(out_file, sep=";", index=False)

    print(f"[INFO] Relatório gerado: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Processador de dados INMET")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Anos para processar")
    parser.add_argument("--out-root", type=str, required=True, help="Diretório raiz de saída")
    parser.add_argument("--workers", type=int, default=1, help="Número de workers em paralelo (não implementado ainda)")
    parser.add_argument("--station-filter", type=str, default=None, help="Lista de estações específicas (separadas por vírgula)")
    args = parser.parse_args()

    allowed_stations = None
    if args.station_filter:
        allowed_stations = [code.strip().upper() for code in args.station_filter.split(",")]

    for year in args.years:
        zip_path = download_zip(year, args.out_root)
        
        extract_dir = os.path.join(args.out_root, f"inmet_{year}")
        extract_zip(zip_path, extract_dir)

        for fname in os.listdir(extract_dir):
            if not fname.lower().endswith(".csv"):
                continue
            full_path = os.path.join(extract_dir, fname)

            if allowed_stations:
                code = parse_station_code(fname)
                if code not in allowed_stations:
                    continue

            process_station_file(full_path, args.out_root, year)

        for var in ["total_precipitation", "2m_air_temperature"]:
            compute_completeness_for_year(year, args.out_root, var)

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    main()

