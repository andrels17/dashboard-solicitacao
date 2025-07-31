import os
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import csv
import unidecode
from datetime import timedelta
from st_aggrid import AgGrid, GridOptionsBuilder

# ------------------------------------------------------------
# 0. Configurações Iniciais e Tema
# ------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard de Follow-up de Frotas",
    layout="wide",
    initial_sidebar_state="collapsed"
)
PRIMARY_COLOR = "#1f77b4"
ALERT_COLOR = "#d62728"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
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
    st.write(f"**{label}**")
    select_all = st.checkbox("Selecionar tudo", value=default, key=f"{label}_all")
    if select_all:
        return options.copy()
    selected = []
    for opt in options:
        if st.checkbox(opt, value=False, key=f"{label}_{opt}"):
            selected.append(opt)
    return selected

@st.cache_data(ttl=3600)
def preprocessar(df: pd.DataFrame, freq: str, date_range: tuple):
    d0, d1 = date_range
    mask = df['Data da Solicitação'].between(pd.to_datetime(d0), pd.to_datetime(d1))
    dff = df.loc[mask].copy()
    dff["periodo"] = dff["Data da Solicitação"].dt.to_period(freq).dt.to_timestamp()
    return dff

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
# 2. Padroniza colunas e tipos
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

df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
if "Valor Último" in df and "Qtd. Solicitada" in df:
    df['Valor Último']    = pd.to_numeric(df['Valor Último'], errors='coerce')
    df['Qtd. Solicitada'] = pd.to_numeric(df['Qtd. Solicitada'], errors='coerce')
    df['Valor']           = df['Valor Último'] * df['Qtd. Solicitada']
if 'Dias em Situação' in df:
    df['Dias em Situação'] = pd.to_numeric(df['Dias em Situação'], errors='coerce')

# ------------------------------------------------------------
# 3. Sidebar: filtros & opções adicionais
# ------------------------------------------------------------
with st.sidebar:
    st.title("Filtros & Opções")
    st.markdown("---")

    tema = st.selectbox("🎨 Tema Plotly", ["plotly_white", "plotly_dark"])
    sla_threshold = st.slider("⚡ SLA Threshold (dias)", 1, 30, 7)
    st.markdown("---")

    st.subheader("📎 Info do CSV")
    st.write(f"Separador: `{sep}`")
    st.write(f"Colunas detectadas: {ncols}")
    st.write(f"Linhas válidas: {n_validas}")
    st.write(f"Linhas inválidas: {n_invalidas}")
    st.markdown("---")

    # Período e granularidade
    datas = df['Data da Solicitação'].dropna()
    if not datas.empty:
        min_date = datas.min().date()
        max_date = datas.max().date()
    else:
        today = datetime.date.today()
        min_date = max_date = today

    data_inicio, data_fim = st.date_input(
        "📅 Período",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    freq = st.radio(
        "📊 Agregação",
        ["D", "W", "M"],
        format_func=lambda x: {"D":"Diária","W":"Semanal","M":"Mensal"}[x]
    )
    st.markdown("---")

    # Filtros categóricos
    equip_list = df['Cód.Equipamento'].dropna().astype(str).unique().tolist()
    sel_equip  = checkbox_filter("Equipamentos", equip_list)

    tipo_list = df.get('TIPO', pd.Series()).dropna().unique().tolist()
    sel_tipo  = checkbox_filter("Tipo", tipo_list) if tipo_list else []

    sit_list = df.get('SITUAÇÃO', pd.Series()).dropna().unique().tolist()
    sel_sit   = checkbox_filter("Situação", sit_list) if sit_list else []

    forn_list = df.get('Fornecedor', pd.Series()).dropna().unique().tolist()
    sel_forn  = checkbox_filter("Fornecedor", forn_list) if forn_list else []

    st.markdown("---")

# ------------------------------------------------------------
# 4. Aplica filtros e segmentação temporal
# ------------------------------------------------------------
mask = (
    df['Data da Solicitação'].between(pd.to_datetime(data_inicio), pd.to_datetime(data_fim)) &
    df['Cód.Equipamento'].astype(str).isin(sel_equip)
)
if sel_tipo: mask &= df['TIPO'].isin(sel_tipo)
if sel_sit:  mask &= df['SITUAÇÃO'].isin(sel_sit)
if sel_forn: mask &= df['Fornecedor'].isin(sel_forn)

df_f   = df.loc[mask].copy()
df_seg = preprocessar(df, freq, (data_inicio, data_fim))

# ------------------------------------------------------------
# 5. Calcula KPIs atuais x período anterior
# ------------------------------------------------------------
reg_atual = len(df_f)
reg_prev  = len(df[
    df['Data da Solicitação']
    .between(
        pd.to_datetime(data_inicio - (data_fim-data_inicio) - timedelta(days=1)),
        pd.to_datetime(data_inicio - timedelta(days=1))
    )
])
sol_atual  = df_f['Cód.Equipamento'].nunique()
pend_atual = df_f.loc[df_f.get('Qtd. Pendente',0) > 0,'Cód.Equipamento'].nunique()
sol_prev   = df['Cód.Equipamento'].nunique()
pend_prev  = df.loc[df.get('Qtd. Pendente',0) > 0,'Cód.Equipamento'].nunique()
sla_atual  = (df_f['Dias em Situação'] <= sla_threshold).mean() if 'Dias em Situação' in df_f else np.nan

# ------------------------------------------------------------
# 6. Layout com Tabs
# ------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📍 KPIs", "📊 Gráficos", "📋 Tabela"])

with tab1:
    st.markdown("### Principais KPIs")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📝 Registros", reg_atual, delta=reg_atual-reg_prev)
    c2.metric("🔢 Solicitados (distintos)", sol_atual, delta=sol_atual-sol_prev)
    c3.metric("⏳ Pendentes (distintos)", pend_atual, delta=pend_atual-pend_prev)
    c4.metric(f"✅ SLA (≤{sla_threshold}d)",
              f"{sla_atual:.1%}",
              delta=f"{sla_atual - 0.8:.1%}")
    pend_pct = pend_atual/sol_atual if sol_atual else 0
    if pend_pct > 0.2:
        st.warning(f"Atenção: {pend_pct:.1%} pendentes (>20%)")

with tab2:
    st.markdown("### Gráficos Avançados")

    # 2.1 Pedidos por período
    hist = (
        df_f['Data da Solicitação']
        .dt.to_period(freq)
        .dt.to_timestamp()
        .value_counts()
        .sort_index()
        .rename_axis("periodo")
        .reset_index(name="Qtde")
    )
    fig_hist = px.bar(hist, x='periodo', y='Qtde',
                      title="Pedidos por Período", template=tema,
                      color_discrete_sequence=[PRIMARY_COLOR])
    st.plotly_chart(fig_hist, use_container_width=True)

    # 2.2 Box-Plot de atrasos
    if 'Dias em Situação' in df_f:
        fig_box = px.box(df_f, x="Cód.Equipamento", y="Dias em Situação",
                         title="Distribuição de Atrasos por Equipamento",
                         template=tema)
        st.plotly_chart(fig_box, use_container_width=True)

    # 2.3 Pareto de pendências
    if 'Qtd. Pendente' in df_f:
        pend = df_f.groupby("Cód.Equipamento")["Qtd. Pendente"]\
                   .sum().sort_values(ascending=False)
        cum_pct = pend.cumsum()/pend.sum()
        fig_pareto = go.Figure([
            go.Bar(x=pend.index, y=pend.values, name="Pendentes", marker_color=PRIMARY_COLOR),
            go.Scatter(x=pend.index, y=cum_pct, name="Acumulado %",
                       yaxis="y2", line_color=ALERT_COLOR)
        ])
        fig_pareto.update_layout(
            title="Pareto de Equipamentos Pendentes",
            yaxis=dict(title="Qtd. Pendentes"),
            yaxis2=dict(overlaying="y", side="right", title="Acumulado %", tickformat=".0%"),
            template=tema
        )
        st.plotly_chart(fig_pareto, use_container_width=True)

    # 2.4 Scatter Valor × Dias
    if 'Valor' in df_f and 'Dias em Situação' in df_f:
        fig_scat = px.scatter(df_f, x="Valor", y="Dias em Situação",
                              color="SITUAÇÃO" if 'SITUAÇÃO' in df_f else None,
                              size="Qtd. Solicitada" if 'Qtd. Solicitada' in df_f else None,
                              title="Valor da Solicitação vs Dias em Situação",
                              template=tema, hover_data=["Cód.Equipamento"])
        st.plotly_chart(fig_scat, use_container_width=True)

    # 2.5 Gastos por Tipo de Material
    if 'Valor' in df_f and 'TIPO' in df_f:
        gastos_tipo = df_f.groupby('TIPO')['Valor'].sum().reset_index()
        fig_gastos = px.bar(gastos_tipo, x='TIPO', y='Valor',
                            title="💰 Gastos por Tipo de Material",
                            template=tema,
                            color='TIPO',
                            color_discrete_sequence=px.colors.qualitative.Plotly)
        st.plotly_chart(fig_gastos, use_container_width=True)

    # 2.6 Percentual de Pedidos por Tipo (Pizza)
    if 'TIPO' in df_f:
        pedidos_tipo = (df_f['TIPO']
                        .value_counts()
                        .reset_index()
                        .rename(columns={'index':'TIPO','TIPO':'Qtde'}))
        fig_pie = px.pie(pedidos_tipo, names='TIPO', values='Qtde',
                         title="🥧 Percentual de Pedidos por Tipo",
                         template=tema,
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

with tab3:
    st.markdown("### Detalhamento Interativo")
    gb = GridOptionsBuilder.from_dataframe(df_f)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    AgGrid(df_f, gridOptions=gb.build(), theme="alpine")
    st.download_button("📥 Exportar CSV Filtrado", df_f.to_csv(index=False), "filtro_export.csv")
