import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode
from datetime import timedelta
from st_aggrid import AgGrid, GridOptionsBuilder
import os

# 1. CARREGA/VALIDA CSV (igual ao que já tens)
@st.cache_data
def carregar_e_validar_csv(arquivo_original, arquivo_limpo):
    def detectar_configuracao_csv(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            primeira = f.readline()
            sep = ";" if ";" in primeira else "," 
            n_colunas = len(primeira.strip().split(sep))
        return sep, n_colunas

    sep, n_colunas = detectar_configuracao_csv(arquivo_original)
    linhas_validas, linhas_invalidas = [], []
    with open(arquivo_original, "r", encoding="utf-8") as f_in:
        leitor = csv.reader(f_in, delimiter=sep)
        for linha in leitor:
            if len(linha) == n_colunas:
                linhas_validas.append(linha)
            else:
                linhas_invalidas.append(linha)
    with open(arquivo_limpo, "w", encoding="utf-8", newline="") as f_out:
        csv.writer(f_out, delimiter=sep).writerows(linhas_validas)
    df = pd.read_csv(arquivo_limpo, sep=sep, encoding="utf-8")
    return df, sep, n_colunas, linhas_validas, linhas_invalidas

# caminhos
arquivo_orig  = "solicitacao_to.csv"
arquivo_limpo = "csv_validado.csv"

if not os.path.exists(arquivo_orig):
    st.error(f"Arquivo não encontrado em: {arquivo_orig}")
    st.stop()

# load
df, sep, n_colunas, validas, invalidas = carregar_e_validar_csv(arquivo_orig, arquivo_limpo)

# --- DEBUG: veja colunas e primeiras linhas
st.write("### Colunas carregadas:", df.columns.tolist())
st.write("### Head do DataFrame:", df.head())

# renomeação, conversão de datas, cálculo de valores… (igual ao seu código atual)
# …

# 2. SIDEBAR: monte os filtros, mas já debugue os defaults
with st.sidebar:
    st.markdown("## Filtros em Debug")
    if "TIPO" in df.columns:
        tipos = df["TIPO"].dropna().unique().tolist()
    else:
        tipos = []
    sel_tipo = st.multiselect("TIPO (debug)", tipos, default=tipos)
    st.write("Defaults TIPO:", tipos)

    if "SITUAÇÃO" in df.columns:
        situacoes = df["SITUAÇÃO"].dropna().unique().tolist()
    else:
        situacoes = []
    sel_sit = st.multiselect("SITUAÇÃO (debug)", situacoes, default=situacoes)
    st.write("Defaults SITUAÇÃO:", situacoes)

    if "Fornecedor" in df.columns:
        fornecedores = df["Fornecedor"].dropna().unique().tolist()
    else:
        fornecedores = []
    sel_forn = st.multiselect("Fornecedor (debug)", fornecedores, default=fornecedores)
    st.write("Defaults Fornecedor:", fornecedores)

    equipamentos = df["Cód.Equipamento"].dropna().astype(str).unique().tolist()
    sel_equip = st.multiselect("Equipamentos (debug)", equipamentos, default=equipamentos)
    st.write("Defaults Equipamentos:", equipamentos)

    min_date, max_date = (
        df["Data da Solicitação"].min(),
        df["Data da Solicitação"].max(),
    )
    data_inicio, data_fim = st.date_input("Período (debug)", [min_date, max_date])
    st.write("Defaults Período:", min_date, "—", max_date)

# 3. APLICAÇÃO DOS FILTROS (somente se a coluna existir)
mask = pd.Series(True, index=df.index)

# data
mask &= df["Data da Solicitação"].between(data_inicio, data_fim)

# Cód.Equipamento
mask &= df["Cód.Equipamento"].astype(str).isin(sel_equip)

# TIPO
if "TIPO" in df.columns:
    mask &= df["TIPO"].isin(sel_tipo)

# SITUAÇÃO
if "SITUAÇÃO" in df.columns:
    mask &= df["SITUAÇÃO"].isin(sel_sit)

# Fornecedor
if "Fornecedor" in df.columns:
    mask &= df["Fornecedor"].isin(sel_forn)

df_f = df[mask].copy()
st.write(f"### Registros após filtros: {len(df_f)}")

