import os
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode
from datetime import timedelta
from st_aggrid import AgGrid, GridOptionsBuilder

# 1. CARREGA E VALIDA CSV
@st.cache_data
def carregar_e_validar_csv(origem, destino):
    def detectar_config(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            primeira = f.readline()
            sep = ";" if ";" in primeira else ","
            ncols = len(primeira.strip().split(sep))
        return sep, ncols

    sep, ncols = detectar_config(origem)
    validas, invalidas = [], []
    with open(origem, "r", encoding="utf-8") as f_in:
        leitor = csv.reader(f_in, delimiter=sep)
        for linha in leitor:
            (validas if len(linha) == ncols else invalidas).append(linha)

    with open(destino, "w", encoding="utf-8", newline="") as f_out:
        csv.writer(f_out, delimiter=sep).writerows(validas)

    df = pd.read_csv(destino, sep=sep, encoding="utf-8")
    return df, sep, ncols, len(validas), len(invalidas)

# caminhos
origem  = "solicitacao_to.csv"
destino = "csv_validado.csv"

if not os.path.exists(origem):
    st.error(f"Arquivo não encontrado: {origem}")
    st.stop()

df, sep, ncols, n_validas, n_invalidas = carregar_e_validar_csv(origem, destino)

# 2. CONFIG DA PÁGINA
st.set_page_config(page_title="Dashboard de Follow-up de Frotas", layout="wide")
st.title("🚛 Dashboard de Follow-up de Frotas")

# 3. RENAME & TYPES
df.rename(columns=lambda c: c.strip(), inplace=True)
mapp = {}
for col in df.columns:
    key = unidecode.unidecode(col.lower().replace(" ", "").replace(".", ""))
    if "qtde" in key and "pendente" not in key:
        mapp[col] = "Qtd. Solicitada"
    elif "pendente" in key:
        mapp[col] = "Qtd. Pendente"
    elif "diaspentrega" in key or "diasparaocseragerada" in key:
        mapp[col] = "Dias em Situação"
    elif "valorultimacompra" in key or "ultimovalor" in key:
        mapp[col] = "Valor Último"
df.rename(columns=mapp, inplace=True)
df = df.loc[:, ~df.columns.duplicated()]

df["Data da Solicitação"] = pd.to_datetime(df["Data da Solicitação"], errors="coerce")
if "Valor Último" in df and "Qtd. Solicitada" in df:
    df["Valor Último"]    = pd.to_numeric(df["Valor Último"], errors="coerce")
    df["Qtd. Solicitada"] = pd.to_numeric(df["Qtd. Solicitada"], errors="coerce")
    df["Valor"]           = df["Valor Último"] * df["Qtd. Solicitada"]

if "Dias em Situação" in df:
    df["Dias em Situação"] = pd.to_numeric(df["Dias em Situação"], errors="coerce")

# 4. SIDEBAR: tema + filtros
with st.sidebar:
    tema = st.selectbox("🎨 Tema dos Gráficos", ["plotly_white", "plotly_dark"])
    st.markdown("---")
    st.subheader("📎 Info do CSV")
    st.write(f"Separador: `{sep}`")
    st.write(f"Colunas detectadas: {ncols}")
    st.write(f"Linhas válidas: {n_validas}")
    st.write(f"Linhas inválidas: {n_invalidas}")
    st.markdown("---")

    # DATAS
    datas = df["Data da Solicitação"].dropna()
    if not datas.empty:
        min_date = datas.min().date()
        max_date = datas.max().date()
    else:
        hoje = datetime.date.today()
        min_date = max_date = hoje

    data_inicio, data_fim = st.date_input(
        "Período",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # EQUIPAMENTOS
    equip_list = df["Cód.Equipamento"].dropna().astype(str).unique().tolist()
    sel_equip   = st.multiselect("Equipamentos", equip_list, default=equip_list)

    # TIPO
    if "TIPO" in df:
        tipo_list = df["TIPO"].dropna().unique().tolist()
        sel_tipo  = st.multiselect("Tipo", tipo_list, default=tipo_list)
    else:
        sel_tipo = []

    # SITUAÇÃO
    if "SITUAÇÃO" in df:
        sit_list  = df["SITUAÇÃO"].dropna().unique().tolist()
        sel_sit   = st.multiselect("Situação", sit_list, default=sit_list)
    else:
        sel_sit = []

    # FORNECEDOR
    if "Fornecedor" in df:
        forn_list = df["Fornecedor"].dropna().unique().tolist()
        sel_forn  = st.multiselect("Fornecedor", forn_list, default=forn_list)
    else:
        sel_forn = []

# 5. APLICA FILTROS SÓ SE HOUVER SELEÇÃO
mask = pd.Series(True, index=df.index)

# data
mask &= df["Data da Solicitação"].between(
    pd.to_datetime(data_inicio), pd.to_datetime(data_fim)
)

# equipamento
if sel_equip:
    mask &= df["Cód.Equipamento"].astype(str).isin(sel_equip)

# tipo
if sel_tipo:
    mask &= df["TIPO"].isin(sel_tipo)

# situação
if sel_sit:
    mask &= df["SITUAÇÃO"].isin(sel_sit)

# fornecedor
if sel_forn:
    mask &= df["Fornecedor"].isin(sel_forn)

df_f = df[mask].copy()

# botão download
with st.sidebar:
    st.markdown("---")
    st.write(f"🔎 Registros filtrados: {len(df_f)}")
    st.download_button("📥 Exportar CSV", df_f.to_csv(index=False), "export.csv")

# 6. MÉTRICAS
def calcular_metricas(d):
    return {
        "qtd_sol":  int(d["Qtd. Solicitada"].sum() or 0),
        "qtd_pen":  int(d.get("Qtd. Pendente", pd.Series(dtype=int)).sum() or 0),
        "valor":    float(d.get("Valor", pd.Series(dtype=float)).sum() or 0.0),
        "dias_med": float(d["Dias em Situação"].mean() or 0.0)
                    if "Dias em Situação" in d else 0.0,
    }

met_atual = calcular_metricas(df_f)
delta     = data_fim - data_inicio
prev_start= data_inicio - delta - timedelta(days=1)
prev_end  = data_inicio - timedelta(days=1)

df_prev = df[
    df["Data da Solicitação"]
      .between(pd.to_datetime(prev_start), pd.to_datetime(prev_end))
]
met_prev = calcular_metricas(df_prev)

# 7. TABS
aba1, aba2, aba3 = st.tabs(["📍 KPIs", "📊 Gráficos", "📋 Tabela Interativa"])

with aba1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Solicitado", met_atual["qtd_sol"],
              delta=met_atual["qtd_sol"]-met_prev["qtd_sol"])
    c2.metric("⏳ Pendentes", met_atual["qtd_pen"],
              delta=met_atual["qtd_pen"]-met_prev["qtd_pen"])
    c3.metric("💸 Valor Total",
              f"R$ {met_atual['valor']:,.2f}",
              delta=f"R$ {met_atual['valor']-met_prev['valor']:,.2f}")
    c4.metric("📅 Média Dias",
              f"{met_atual['dias_med']:.1f} dias",
              delta=f"{met_atual['dias_med']-met_prev['dias_med']:+.1f} dias")
    st.caption("Comparação com o período anterior")

with aba2:
    st.subheader("📊 Pedidos por Dia")
    df_hist = (
        df_f["Data da Solicitação"]
        .dt.date
        .value_counts()
        .sort_index()
        .rename_axis("Data")
        .reset_index(name="Qtde")
    )
    fig_tl = px.bar(df_hist, x="Data", y="Qtde",
                    title="🗓️ Pedidos por Dia",
                    template=tema)
    st.plotly_chart(fig_tl, use_container_width=True)

    # outros gráficos (aging, top10 gastos/pendências)…
    # (mantenha a mesma lógica de só plotar se a coluna existir)

with aba3:
    st.subheader("📋 Tabela Interativa")
    gb = GridOptionsBuilder.from_dataframe(df_f)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    AgGrid(df_f, gridOptions=gb.build(),
           enable_enterprise_modules=True, theme="alpine")
