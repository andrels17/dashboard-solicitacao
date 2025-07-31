import streamlit as st
import pandas as pd
import plotly.express as px

# 🗂️ Carregar e limpar dados
df = pd.read_csv("solicitacao_to.csv", encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)

# ✅ Validação de colunas
colunas_esperadas = [
    'Mês', 'TIPO', 'Descrição', 'Qtde. Solicitada', 'Qtde. Entregue',
    'Qtde. Pendente', 'OC', 'Status', 'Data da Solicitação', 'Fornecedor'
]
faltando = [col for col in colunas_esperadas if col not in df.columns]
if faltando:
    st.error(f"❌ Colunas faltando no CSV: {faltando}")
    st.stop()

# 🕒 Conversão de data
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df = df.dropna(subset=['Mês', 'TIPO', 'Data da Solicitação'])

# 🖼️ Título
st.title("📊 Dashboard de Solicitações TO")

# 🎛️ Filtros interativos
meses = sorted(df['Mês'].unique())
tipos = sorted(df['TIPO'].unique())
fornecedores = sorted(df['Fornecedor'].dropna().unique())
data_min = df['Data da Solicitação'].min()
data_max = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("🔎 Filtros")
    mes_filtrado = st.selectbox("Mês", meses)
    tipo_filtrado = st.selectbox("Tipo", tipos)
    fornecedor_filtrado = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    data_inicio, data_fim = st.date_input("Intervalo de Datas", [data_min, data_max])

# 🔎 Aplicação dos filtros
filtro = (
    (df['Mês'] == mes_filtrado) &
    (df['TIPO'] == tipo_filtrado) &
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if fornecedor_filtrado != "Todos":
    filtro &= (df['Fornecedor'] == fornecedor_filtrado)

df_filtrado = df[filtro].copy().sort_values(by='Qtde. Pendente', ascending=False)
df_filtrado['Alerta'] = df_filtrado['Qtde. Pendente'].apply(lambda x: '⚠️' if x > 50 else '')

# 📚 Abas
aba_kpis, aba_graficos, aba_tabela = st.tabs(["📍 Indicadores", "📊 Gráficos", "📋 Tabela"])

with aba_kpis:
    st.subheader("📍 Indicadores")
    total_solicitado = df_filtrado['Qtde. Solicitada'].sum()
    total_entregue = df_filtrado['Qtde. Entregue'].sum()
    total_pendente = df_filtrado['Qtde. Pendente'].sum()
    perc_oc = (df_filtrado['OC'] == 'Tem OC').mean() * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Solicitado", f"{int(total_solicitado):,}")
    col2.metric("Entregue", f"{int(total_entregue):,}")
    col3.metric("Pendente", f"{int(total_pendente):,}")
    col4.metric("% com OC", f"{perc_oc:.1f}%")

with aba_graficos:
    st.subheader("📊 Visualizações")

    df_top_pendentes = df_filtrado.groupby('Descrição')['Qtde. Pendente'].sum().nlargest(10).reset_index()
    fig1 = px.bar(df_top_pendentes, x='Qtde. Pendente', y='Descrição', orientation='h', title='Top 10 Materiais Pendentes')
    st.plotly_chart(fig1)

    fig2 = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
    st.plotly_chart(fig2)

    df_trend = df_filtrado.copy()
    df_trend['AnoMes'] = df_trend['Data da Solicitação'].dt.to_period("M").astype(str)
    df_line = df_trend.groupby('AnoMes')['Qtde. Pendente'].sum().reset_index()
    fig3 = px.line(df_line, x='AnoMes', y='Qtde. Pendente', markers=True, title="Pendências por Mês")
    st.plotly_chart(fig3)

    df_for = df_filtrado.groupby('Fornecedor')['Qtde. Pendente'].sum().reset_index()
    fig4 = px.scatter(df_for, x='Fornecedor', y='Qtde. Pendente', size='Qtde. Pendente', title='Pendência por Fornecedor')
    st.plotly_chart(fig4)

with aba_tabela:
    st.subheader("📋 Dados Filtrados")
    st.caption(f"{len(df_filtrado)} registros encontrados")
    st.dataframe(df_filtrado[
        ['Alerta', 'Data da Solicitação', 'Descrição', 'Fornecedor', 'Qtde. Solicitada',
         'Qtde. Pendente', 'OC', 'Status']
    ])
    csv = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar dados filtrados", csv, "dados_filtrados.csv", "text/csv")
