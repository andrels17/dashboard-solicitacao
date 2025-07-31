import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import os

# 📁 Arquivo original
arquivo_original = "solicitacao_to.csv"
arquivo_limpo = "csv_validado.csv"
num_colunas_esperadas = 10  # ajuste se necessário
delimitador = ","  # ajuste se for ";"

# 🔍 Validação do CSV
def validar_csv(entrada, saida, colunas_esperadas):
    linhas_validas = []
    linhas_invalidas = []
    with open(entrada, "r", encoding="utf-8") as f_in:
        leitor = csv.reader(f_in, delimiter=delimitador)
        for i, linha in enumerate(leitor, start=1):
            if len(linha) == colunas_esperadas:
                linhas_validas.append(linha)
            else:
                linhas_invalidas.append((i, linha))

    with open(saida, "w", encoding="utf-8", newline='') as f_out:
        escritor = csv.writer(f_out, delimiter=delimitador)
        for linha in linhas_validas:
            escritor.writerow(linha)

    return linhas_validas, linhas_invalidas

# 🛡️ Executa validação
linhas_validas, linhas_invalidas = validar_csv(arquivo_original, arquivo_limpo, num_colunas_esperadas)

# 🧾 Feedback da validação
st.sidebar.subheader("✅ Verificação do CSV")
st.sidebar.write(f"Linhas válidas: {len(linhas_validas)}")
st.sidebar.write(f"Linhas com erro: {len(linhas_invalidas)}")

if linhas_invalidas:
    with st.expander("🔍 Ver linhas com erro"):
        for i, linha in linhas_invalidas[:10]:  # exibe até 10
            st.write(f"Linha {i}: {linha}")

# 📈 Carregamento do CSV limpo
df = pd.read_csv(arquivo_limpo, encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)

# ✅ Confere colunas obrigatórias
colunas_esperadas = [
    'Mês', 'TIPO', 'Descrição', 'Qtde. Solicitada', 'Qtde. Entregue',
    'Qtde. Pendente', 'OC', 'Status', 'Data da Solicitação', 'Fornecedor'
]
faltando = [col for col in colunas_esperadas if col not in df.columns]
if faltando:
    st.error(f"❌ Colunas faltando: {faltando}")
    st.stop()

df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df = df.dropna(subset=['Mês', 'TIPO', 'Data da Solicitação'])

# 🖼️ Título
st.title("📊 Dashboard de Solicitações TO")

# 🎛️ Filtros
meses = sorted(df['Mês'].dropna().unique())
tipos = sorted(df['TIPO'].dropna().unique())
fornecedores = sorted(df['Fornecedor'].dropna().unique())
data_min = df['Data da Solicitação'].min()
data_max = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("📌 Filtros")
    mes = st.selectbox("Mês", meses)
    tipo = st.selectbox("Tipo", tipos)
    fornecedor = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])

# 🔎 Aplicação de filtros
filtro = (
    (df['Mês'] == mes) &
    (df['TIPO'] == tipo) &
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if fornecedor != "Todos":
    filtro &= (df['Fornecedor'] == fornecedor)

df_filtrado = df[filtro].copy().sort_values(by='Qtde. Pendente', ascending=False)
df_filtrado['Alerta'] = df_filtrado['Qtde. Pendente'].apply(lambda x: '⚠️' if x > 50 else '')

# 📚 Abas
aba1, aba2, aba3 = st.tabs(["📍 Indicadores", "📊 Gráficos", "📋 Tabela"])

with aba1:
    st.subheader("📍 Indicadores")
    st.metric("Solicitado", f"{int(df_filtrado['Qtde. Solicitada'].sum()):,}")
    st.metric("Entregue", f"{int(df_filtrado['Qtde. Entregue'].sum()):,}")
    st.metric("Pendente", f"{int(df_filtrado['Qtde. Pendente'].sum()):,}")
    st.metric("% com OC", f"{(df_filtrado['OC'] == 'Tem OC').mean() * 100:.1f}%")

with aba2:
    st.subheader("📊 Visualizações")
    fig1 = px.bar(
        df_filtrado.groupby('Descrição')['Qtde. Pendente'].sum().nlargest(10).reset_index(),
        x='Qtde. Pendente', y='Descrição', orientation='h', title='Top 10 Materiais Pendentes'
    )
    st.plotly_chart(fig1)

    fig2 = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
    st.plotly_chart(fig2)

    df_trend = df_filtrado.copy()
    df_trend['AnoMes'] = df_trend['Data da Solicitação'].dt.to_period("M").astype(str)
    fig3 = px.line(
        df_trend.groupby('AnoMes')['Qtde. Pendente'].sum().reset_index(),
        x='AnoMes', y='Qtde. Pendente', markers=True, title="Pendências por Mês"
    )
    st.plotly_chart(fig3)

    fig4 = px.scatter(
        df_filtrado.groupby('Fornecedor')['Qtde. Pendente'].sum().reset_index(),
        x='Fornecedor', y='Qtde. Pendente', size='Qtde. Pendente', title='Pendência por Fornecedor'
    )
    st.plotly_chart(fig4)

with aba3:
    st.subheader("📋 Dados Filtrados")
    st.caption(f"{len(df_filtrado)} registros encontrados")
    st.dataframe(df_filtrado[
        ['Alerta', 'Data da Solicitação', 'Descrição', 'Fornecedor',
         'Qtde. Solicitada', 'Qtde. Pendente', 'OC', 'Status']
    ])
    st.download_button("📥 Baixar CSV filtrado", df_filtrado.to_csv(index=False).encode('utf-8'),
                       "dados_filtrados.csv", "text/csv")

