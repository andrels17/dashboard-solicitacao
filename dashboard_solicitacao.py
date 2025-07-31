import os
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode
from datetime import timedelta
from st_aggrid import AgGrid, GridOptionsBuilder

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
@st.cache_data
def carregar_e_validar_csv(origem: str, destino: str):
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

def checkbox_filter(label: str, options: list[str], default: bool = True) -> list[str]:
    """
    Exibe na sidebar:
      - Checkbox 'Selecionar tudo'
      - Lista de checkboxes individuais (se desmarcar 'Selecionar tudo')
    Retorna a lista de opções selecionadas.
    """
    st.write(f"**{label}**")
    select_all = st.checkbox("Selecionar tudo", value=default, key=f"{label}_all")
    if select_all:
        return options.copy()
    selected = []
    for opt in options:
        if st.checkbox(opt, value=False, key=f"{label}_{opt}"):
            selected.append(opt)
    return selected

# ------------------------------------------------------------
# 1. Carrega & valida CSV
# ------------------------------------------------------------
origem  = "solicitacao_to.csv"
destino = "csv_validado.csv"
if not os.path.exists(origem):
    st.error(f"Arquivo não encontrado: {origem}")
    st.stop()

df, sep, ncols, n_validas, n_invalidas = carregar_e_validar_csv(origem, destino)

# ------------------------------------------------------------
# 2. Configura página
# ------------------------------------------------------------
st.set_page_config(page_title="Dashboard de Follow-up de Frotas", layout="wide")
st.title("🚛 Dashboard de Follow-up de Frotas")

# ------------------------------------------------------------
# 3. Padroniza colunas e tipos
# ------------------------------------------------------------
df.rename(columns=lambda c: c.strip(), inplace=True)
rename_map = {}
for col in df.columns:
    key = unidecode.unidecode(col.lower().replace(" ", "").replace(".", ""))
    if "qtde" in key and "pendente" not in key:
        rename_map[col] = "Qtd. Solicitada"
    elif "pendente" in key:
        rename_map[col] = "Qtd. Pendente"
    elif "diaspentrega" in key or "diasparaocseragerada" in key:
        rename_map[col] = "Dias em Situação"
    elif "valorultimacompra" in key or "ultimovalor" in key:
        rename_map[col] = "Valor Último"
df.rename(columns=rename_map, inplace=True)
df = df.loc[:, ~df.columns.duplicated()]

# conversões
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
if "Valor Último" in df and "Qtd. Solicitada" in df:
    df['Valor Último']    = pd.to_numeric(df['Valor Último'], errors='coerce')
    df['Qtd. Solicitada'] = pd.to_numeric(df['Qtd. Solicitada'], errors='coerce')
    df['Valor']           = df['Valor Último'] * df['Qtd. Solicitada']
if 'Dias em Situação' in df:
    df['Dias em Situação'] = pd.to_numeric(df['Dias em Situação'], errors='coerce')

# ------------------------------------------------------------
# 4. Sidebar: Tema e filtros
# ------------------------------------------------------------
with st.sidebar:
    tema = st.selectbox("🎨 Tema dos Gráficos", ["plotly_white", "plotly_dark"])
    st.markdown("---")
    st.subheader("📎 Info do CSV")
    st.write(f"Separador: `{sep}`")
    st.write(f"Colunas detectadas: {ncols}")
    st.write(f"Linhas válidas: {n_validas}")
    st.write(f"Linhas inválidas: {n_invalidas}")
    st.markdown("---")

    # Período
    datas = df['Data da Solicitação'].dropna()
    if not datas.empty:
        min_date = datas.min().date()
        max_date = datas.max().date()
    else:
        today = datetime.date.today()
        min_date = max_date = today

    data_inicio, data_fim = st.date_input(
        "Período",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    st.markdown("---")

    # Equipamentos
    equip_list = df['Cód.Equipamento'].dropna().astype(str).unique().tolist()
    sel_equip  = checkbox_filter("Equipamentos", equip_list)

    # Tipo
    if 'TIPO' in df:
        tipo_list = df['TIPO'].dropna().unique().tolist()
        sel_tipo  = checkbox_filter("Tipo", tipo_list)
    else:
        sel_tipo = []

    # Situação
    if 'SITUAÇÃO' in df:
        sit_list = df['SITUAÇÃO'].dropna().unique().tolist()
        sel_sit  = checkbox_filter("Situação", sit_list)
    else:
        sel_sit = []

    # Fornecedor
    if 'Fornecedor' in df:
        forn_list = df['Fornecedor'].dropna().unique().tolist()
        sel_forn  = checkbox_filter("Fornecedor", forn_list)
    else:
        sel_forn = []

# ------------------------------------------------------------
# 5. Aplica filtros
# ------------------------------------------------------------
mask = pd.Series(True, index=df.index)
mask &= df['Data da Solicitação'].between(
    pd.to_datetime(data_inicio), pd.to_datetime(data_fim)
)
mask &= df['Cód.Equipamento'].astype(str).isin(sel_equip)
if sel_tipo:  mask &= df['TIPO'].isin(sel_tipo)
if sel_sit:   mask &= df['SITUAÇÃO'].isin(sel_sit)
if sel_forn:  mask &= df['Fornecedor'].isin(sel_forn)

df_f = df[mask].copy()

with st.sidebar:
    st.markdown("---")
    st.write(f"🔎 Registros filtrados: {len(df_f)}")
    st.download_button("📥 Exportar CSV", df_f.to_csv(index=False), "export.csv")

# ------------------------------------------------------------
# 6. Métricas: agora usando contagens em vez de somas
# ------------------------------------------------------------
def calcular_metricas(d):
    # número de registros (linhas)
    num_registros = len(d)
    # contagem de equipamentos distintos solicitados
    qtd_solicitados = d['Cód.Equipamento'].nunique()
    # contagem de equipamentos pendentes (pendente > 0)
    if 'Qtd. Pendente' in d:
        qtd_pendentes = d.loc[d['Qtd. Pendente'] > 0, 'Cód.Equipamento'].nunique()
    else:
        qtd_pendentes = 0
    # valor total (soma de Valor = unitário × qtd solicitada)
    valor_total = float(d.get('Valor', pd.Series(dtype=float)).sum() or 0.0)

    return {
        'num_reg': num_registros,
        'qtd_solic': qtd_solicitados,
        'qtd_pend': qtd_pendentes,
        'valor': valor_total
    }

metrics_atual = calcular_metricas(df_f)

# período anterior
delta = data_fim - data_inicio
prev_start = pd.to_datetime(data_inicio - delta - timedelta(days=1))
prev_end   = pd.to_datetime(data_inicio - timedelta(days=1))
df_prev = df[
    df['Data da Solicitação'].between(prev_start, prev_end)
]
metrics_prev = calcular_metricas(df_prev)

# ------------------------------------------------------------
# 7. Aba de KPIs, Gráficos e Tabela
# ------------------------------------------------------------
aba1, aba2, aba3 = st.tabs(["📍 KPIs", "📊 Gráficos", "📋 Tabela"])

with aba1:
    st.subheader("📍 Principais KPIs")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        label="📝 Registros",
        value=metrics_atual['num_reg'],
        delta=metrics_atual['num_reg']-metrics_prev['num_reg']
    )
    c2.metric(
        label="🔢 Materiais Solicitados (distintos)",
        value=metrics_atual['qtd_solic'],
        delta=metrics_atual['qtd_solic']-metrics_prev['qtd_solic']
    )
    c3.metric(
        label="⏳ Materiais Pendentes (distintos)",
        value=metrics_atual['qtd_pend'],
        delta=metrics_atual['qtd_pend']-metrics_prev['qtd_pend']
    )
    c4.metric(
        label="💰 Valor Total (R$)",
        value=f"{metrics_atual['valor']:,.2f}",
        delta=f"{metrics_atual['valor']-metrics_prev['valor']:,.2f}"
    )
    st.caption("Comparado ao período anterior")

with aba2:
    st.subheader("Pedidos por Dia")
    df_hist = (
        df_f['Data da Solicitação']
        .dt.date
        .value_counts()
        .sort_index()
        .rename_axis('Data')
        .reset_index(name='Qtde')
    )
    fig = px.bar(df_hist, x='Data', y='Qtde',
                 title="🗓️ Pedidos por Dia", template=tema)
    st.plotly_chart(fig, use_container_width=True)

    # outros gráficos…

with aba3:
    st.subheader("📋 Detalhamento Interativo")
    gb = GridOptionsBuilder.from_dataframe(df_f)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    AgGrid(df_f, gridOptions=gb.build(),
           enable_enterprise_modules=True, theme="alpine")
