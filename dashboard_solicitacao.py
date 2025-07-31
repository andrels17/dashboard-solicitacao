import streamlit as st
import pandas as pd
import plotly.express as px

# Carregar os dados do CSV exportado da aba "Solicitação to"
df = pd.read_csv("solicitacao_to.csv", encoding="utf-8")

# Limpeza de colunas
cols = {col: col.strip() for col in df.columns}
df.rename(columns=cols, inplace=True)

# Título
df = df.dropna(subset=['Mês', 'TIPO'])  # Garante que os filtros funcionem corretamente
st.title("Dashboard de Solicitações TO")

# Filtros
meses = df['Mês'].dropna().unique()
tipos = df['TIPO'].dropna().unique()

col1, col2 = st.columns(2)
mes_filtrado = col1.selectbox("Selecione o mês:", sorted(meses))
tipo_filtrado = col2.selectbox("Selecione o tipo:", sorted(tipos))

# Filtragem
filtro = (df['Mês'] == mes_filtrado) & (df['TIPO'] == tipo_filtrado)
df_filtrado = df[filtro]

# KPIs
total_solicitado = df_filtrado['Qtde. Solicitada'].sum()
total_entregue = df_filtrado['Qtde. Entregue'].sum()
total_pendente = df_filtrado['Qtde. Pendente'].sum()
perc_oc = (df_filtrado['OC'] == 'Tem OC').mean() * 100

st.metric("Total Solicitado", int(total_solicitado))
st.metric("Total Entregue", int(total_entregue))
st.metric("Total Pendente", int(total_pendente))
st.metric("% com OC", f"{perc_oc:.1f}%")

# Gráfico de materiais mais pendentes
df_top_pendentes = df_filtrado.groupby('Descrição')['Qtde. Pendente'].sum().nlargest(10).reset_index()
fig1 = px.bar(df_top_pendentes, x='Qtde. Pendente', y='Descrição', orientation='h', title='Top 10 Materiais Pendentes')
st.plotly_chart(fig1)

# Gráfico de status
fig2 = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
st.plotly_chart(fig2)

# Tabela
st.subheader("Dados Filtrados")
st.dataframe(df_filtrado[['Data da Solicitação', 'Descrição', 'Fornecedor', 'Qtde. Solicitada', 'Qtde. Pendente', 'OC', 'Status']])
