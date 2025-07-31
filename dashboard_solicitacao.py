import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode
import datetime
from datetime import timedelta
from st_aggrid import AgGrid, GridOptionsBuilder
import os

# 1. CARREGA/VALIDA CSV
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
    return df, sep, n_colunas, len(linhas_validas), len(linhas_invalidas)

# caminhos dos arquivos
arquivo_orig  = "solicitacao_to.csv"
arquivo_limpo = "csv_validado.csv"
if not os.path.exists(arquivo_orig):
    st.error(f"Arquivo não encontrado: {arquivo_orig}")
    st.stop()

# carrega o dataframe
df, sep, n_colunas, n_validas, n_invalidas = carregar_e_validar_csv(
    arquivo_orig, arquivo_limpo
)

# 2. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Dashboard de Follow-up de Frotas", layout="wide")
st.title("🚛 Dashboard de Follow-up de Frotas")

# 3. PADRÃO DE NOMES E CONVERSÕES
df.rename(columns=lambda c: c.strip(), inplace=True)
rename_map = {}
for col in df.columns:
    key = unidecode.unidecode(col.lower().replace(" ", "").replace(".", ""))
    if "qtde" in key and "pendente" not in key and "entregue" not in key:
        rename_map[col] = "Qtd. Solicitada"
    elif "pendente" in key:
        rename_map[col] = "Qtd. Pendente"
    elif "diaspentrega" in key or "diasparaocseragerada" in key:
        rename_map[col] = "Dias em Situação"
    elif "valorultimacompra" in key or "ultimovalor" in key:
        rename_map[col] = "Valor Último"
df.rename(columns=rename_map, inplace=True)
df = df.loc[:, ~df.columns.duplicated()]

# converte datas e numéricos
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
if "Valor Último" in df and "Qtd. Solicitada" in df:
    df['Valor Último']    = pd.to_numeric(df['Valor Último'], errors='coerce')
    df['Qtd. Solicitada'] = pd.to_numeric(df['Qtd. Solicitada'], errors='coerce')
    df['Valor']           = df['Valor Último'] * df['Qtd. Solicitada']
if 'Dias em Situação' in df:
    df['Dias em Situação'] = pd.to_numeric(df['Dias em Situação'], errors='coerce')

# 4. SIDEBAR: temas e filtros
with st.sidebar:
    tema = st.selectbox("🎨 Tema dos Gráficos", ["plotly_white", "plotly_dark"])
    st.markdown("---")
    st.subheader("📎 Sobre o CSV")
    st.write(f"Separador: `{sep}`")
    st.write(f"Colunas detectadas: {n_colunas}")
    st.write(f"Linhas válidas: {n_validas}")
    st.write(f"Linhas inválidas: {n_invalidas}")
    st.markdown("---")

    # datas
    datas = df['Data da Solicitação'].dropna()
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

    # Equipamentos
    equipamentos = df['Cód.Equipamento'].dropna().astype(str).unique().tolist()
    sel_equip = st.multiselect("Equipamentos", equipamentos, default=equipamentos)

    # Tipo, Situação, Fornecedor (só se existirem)
    if 'TIPO' in df:
        tipos = df['TIPO'].dropna().unique().tolist()
        sel_tipo = st.multiselect("Tipo", tipos, default=tipos)
    else:
        sel_tipo = []

    if 'SITUAÇÃO' in df:
        situacoes = df['SITUAÇÃO'].dropna().unique().tolist()
        sel_sit = st.multiselect("Situação", situacoes, default=situacoes)
    else:
        sel_sit = []

    if 'Fornecedor' in df:
        fornecedores = df['Fornecedor'].dropna().unique().tolist()
        sel_forn = st.multiselect("Fornecedor", fornecedores, default=fornecedores)
    else:
        sel_forn = []

# 5. APLICAÇÃO DOS FILTROS
mask = pd.Series(True, index=df.index)
mask &= df['Data da Solicitação'].between(
    pd.to_datetime(data_inicio), pd.to_datetime(data_fim)
)
mask &= df['Cód.Equipamento'].astype(str).isin(sel_equip)
if 'TIPO' in df:      mask &= df['TIPO'].isin(sel_tipo)
if 'SITUAÇÃO' in df:  mask &= df['SITUAÇÃO'].isin(sel_sit)
if 'Fornecedor' in df:mask &= df['Fornecedor'].isin(sel_forn)
df_f = df[mask].copy()

# botão de download
with st.sidebar:
    st.markdown("---")
    st.write(f"🔎 Registros filtrados: {len(df_f)}")
    st.download_button(
        "📥 Exportar CSV", df_f.to_csv(index=False), "export.csv", "text/csv"
    )

# 6. CÁLCULO DE MÉTRICAS
def calcular_metricas(dframe):
    stats = {
        'qtd_sol': int(dframe['Qtd. Solicitada'].sum() or 0),
        'qtd_pen': int(dframe.get('Qtd. Pendente', pd.Series(dtype=int)).sum() or 0),
        'valor':   float(dframe.get('Valor', pd.Series(dtype=float)).sum() or 0.0),
        'dias_med': float(dframe['Dias em Situação'].mean() or 0.0)
            if 'Dias em Situação' in dframe else 0.0
    }
    return stats

met_atual = calcular_metricas(df_f)
delta      = data_fim - data_inicio
prev_start = data_inicio - delta - timedelta(days=1)
prev_end   = data_inicio - timedelta(days=1)
df_prev = df[
    df['Data da Solicitação']
      .between(pd.to_datetime(prev_start), pd.to_datetime(prev_end))
]
met_prev = calcular_metricas(df_prev)

# 7. TABS: KPIs, Gráficos, Tabela
aba1, aba2, aba3 = st.tabs(["📍 KPIs", "📊 Gráficos", "📋 Tabela Interativa"])

with aba1:
    st.subheader("📍 Principais KPIs")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Solicitado", met_atual['qtd_sol'],
              delta=met_atual['qtd_sol']-met_prev['qtd_sol'])
    c2.metric("⏳ Pendentes", met_atual['qtd_pen'],
              delta=met_atual['qtd_pen']-met_prev['qtd_pen'])
    c3.metric("💸 Valor Total",
              f"R$ {met_atual['valor']:,.2f}",
              delta=f"R$ {met_atual['valor']-met_prev['valor']:,.2f}")
    c4.metric("📅 Média Dias",
              f"{met_atual['dias_med']:.1f} dias",
              delta=f"{met_atual['dias_med']-met_prev['dias_med']:+.1f} dias")
    st.caption("Comparado ao período anterior")

with aba2:
    st.subheader("📊 Gráficos de Follow-up")

    # gráfico de pedidos por dia
    df_hist = (
        df_f['Data da Solicitação']
        .dt.date
        .value_counts()
        .sort_index()
        .rename_axis('Data')
        .reset_index(name='Qtde')
    )
    fig_tl = px.bar(
        df_hist, x='Data', y='Qtde',
        title="🗓️ Pedidos por Dia",
        labels={'Data':'Data','Qtde':'Qtde'},
        template=tema
    )
    st.plotly_chart(fig_tl, use_container_width=True)

    # aging
    if 'Dias em Situação' in df_f:
        faixas = pd.cut(
            df_f['Dias em Situação'], bins=[0,7,14,30,999],
            labels=["0–7","8–14","15–30",">30"]
        )
        aging = faixas.value_counts().reindex(
            ["0–7","8–14","15–30",">30"]
        ).reset_index()
        aging.columns = ['Faixa','Qtde']
        fig_aging = px.bar(
            aging, x='Faixa', y='Qtde', color='Qtde',
            title="⏳ Aging dos Pedidos", template=tema
        )
        st.plotly_chart(fig_aging, use_container_width=True)

    # top 10 por valor
    if 'Valor' in df_f:
        top_g = df_f.nlargest(10, 'Valor')
        fig_g = px.bar(
            top_g, x='Valor', y='Cód.Equipamento',
            orientation='h', text_auto='.2f', color='Valor',
            color_continuous_scale='Viridis',
            title="🔝 Top 10 Gastos por Equipamento",
            template=tema
        )
        fig_g.update_layout(xaxis_tickformat=',.2f')
        st.plotly_chart(fig_g, use_container_width=True)

    # top 10 pendências
    if 'Qtd. Pendente' in df_f:
        df_f['Qtd. Pendente'] = df_f['Qtd. Pendente'].fillna(0).astype(int)
        top_p = df_f.nlargest(10, 'Qtd. Pendente')
        fig_p = px.bar(
            top_p, x='Qtd. Pendente', y='Cód.Equipamento',
            orientation='h', text_auto='.0f', color='Qtd. Pendente',
            color_continuous_scale='Cividis',
            title="🔝 Top 10 Pendências",
            template=tema
        )
        fig_p.update_layout(xaxis_tickformat=',d')
        st.plotly_chart(fig_p, use_container_width=True)

with aba3:
    st.subheader("📋 Detalhamento e Follow-up")
    gb = GridOptionsBuilder.from_dataframe(df_f)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    grid_opts = gb.build()
    AgGrid(
        df_f, gridOptions=grid_opts,
        enable_enterprise_modules=True,
        theme="alpine"
    )
