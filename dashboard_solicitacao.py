import streamlit as st
import pandas as pd
import plotly.express as px
import csv

# 🔍 Validação do CSV
def detectar_configuracao_csv(arquivo):
    with open(arquivo, "r", encoding="utf-8") as f:
        linha = f.readline()
        sep = ";" if ";" in linha else "," if "," in linha else ","
        n_colunas = len(linha.strip().split(sep))
    return sep, n_colunas

def validar_csv(entrada, saida):
    sep, n_colunas = detectar_configuracao_csv(entrada)
    linhas_validas, linhas_invalidas = [], []
    with open(entrada, "r", encoding="utf-8") as f_in:
        leitor = csv.reader(f_in, delimiter=sep)
        for i, linha in enumerate(leitor, start=1):
            if len(linha) == n_colunas:
                linhas_validas.append(linha)
            else:
                linhas_invalidas.append((i, linha))
    with open(saida, "w", encoding="utf-8", newline='') as f_out:
        escritor = csv.writer(f_out, delimiter=sep)
        escritor.writerows(linhas_validas)
    return sep, n_colunas, linhas_validas, linhas_invalidas

# 📁 Arquivos
arquivo_original = "solicitacao_to.csv"
arquivo_limpo = "csv_validado.csv"
sep, n_colunas, linhas_validas, linhas_invalidas = validar_csv(arquivo_original, arquivo_limpo)

# 📋 Relatório da validação
st.sidebar.subheader("🔎 Validação do CSV")
st.sidebar.write(f"Separador detectado: `{sep}`")
st.sidebar.write(f"Colunas esperadas: {n_colunas}")
st.sidebar.write(f"✔️ Linhas válidas: {len(linhas_validas)}")
st.sidebar.write(f"❌ Linhas com erro: {len(linhas_invalidas)}")
if linhas_invalidas:
    with st.expander("Ver linhas com erro"):
        for i, linha in linhas_invalidas[:10]:
            st.write(f"Linha {i}: {linha}")

# 📈 Carregamento
df = pd.read_csv(arquivo_limpo, sep=sep, encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df = df.dropna(subset=['Mês', 'TIPO', 'Data da Solicitação'])

# 💰 Gera coluna Valor se necessário
if all(col in df.columns for col in ['Combustível', 'Manutenção', 'Peças']):
    df['Valor'] = df[['Combustível', 'Manutenção', 'Peças']].sum(axis=1)

# 🎛️ Filtros
st.title("📊 Dashboard de Solicitações TO")
meses = sorted(df['Mês'].dropna().unique())
tipos = sorted(df['TIPO'].dropna().unique())
fornecedores = sorted(df['Fornecedor'].dropna().unique())
frotas = sorted(df['Frota'].dropna().unique()) if 'Frota' in df.columns else []
data_min = df['Data da Solicitação'].min()
data_max = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("🎛️ Filtros")
    mes = st.selectbox("Mês", meses)
    tipo_selecionado = st.selectbox("Tipo", ["Todos"] + tipos)
    fornecedor = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    frota_selecionada = st.selectbox("Frota", ["Todos"] + frotas) if frotas else "Todos"
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])

# 🔍 Aplicação dos filtros
filtro = (
    (df['Mês'] == mes) &
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if tipo_selecionado != "Todos":
    filtro &= (df['TIPO'] == tipo_selecionado)
if fornecedor != "Todos":
    filtro &= (df['Fornecedor'] == fornecedor)
if frota_selecionada != "Todos":
    filtro &= (df['Frota'] == frota_selecionada)

df_filtrado = df[filtro].copy().sort_values(by='Qtde. Pendente', ascending=False)
df_filtrado['Alerta'] = df_filtrado['Qtde. Pendente'].apply(lambda x: '⚠️' if x > 50 else '')

# 📚 Abas
aba1, aba2, aba3, aba4 = st.tabs(["📍 Indicadores", "📊 Pendências", "📋 Tabela", "💰 Gastos"])

with aba1:
    st.subheader("📍 Indicadores")
    st.metric("Solicitado", f"{int(df_filtrado['Qtde. Solicitada'].sum()):,}")
    st.metric("Entregue", f"{int(df_filtrado['Qtde. Entregue'].sum()):,}")
    st.metric("Pendente", f"{int(df_filtrado['Qtde. Pendente'].sum()):,}")
    st.metric("% com OC", f"{(df_filtrado['OC'] == 'Tem OC').mean() * 100:.1f}%")
    if 'Valor' in df_filtrado.columns:
        st.metric("Gasto Total", f"R$ {df_filtrado['Valor'].sum():,.2f}")

with aba2:
    st.subheader("📊 Pendências")

    fig1 = px.bar(df_filtrado.groupby('Descrição')['Qtde. Pendente'].sum().nlargest(10).reset_index(),
                  x='Qtde. Pendente', y='Descrição', orientation='h', title='Top 10 Pendentes')
    st.plotly_chart(fig1)

    fig2 = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
    st.plotly_chart(fig2)

    df_filtrado['AnoMes'] = df_filtrado['Data da Solicitação'].dt.to_period("M").astype(str)
    pendencia_mes = df_filtrado.groupby('AnoMes')['Qtde. Pendente'].sum().reset_index()
    fig_mes = px.line(pendencia_mes, x='AnoMes', y='Qtde. Pendente', markers=True, title='📅 Pendência Mensal')
    st.plotly_chart(fig_mes)

    pendencia_fornecedor = df_filtrado.groupby('Fornecedor')['Qtde. Pendente'].sum().reset_index()
    fig_fornecedor = px.bar(pendencia_fornecedor.sort_values(by='Qtde. Pendente', ascending=False),
                            x='Qtde. Pendente', y='Fornecedor', orientation='h',
                            title='📦 Pendência por Fornecedor', text_auto=True)
    st.plotly_chart(fig_fornecedor)

with aba3:
    st.subheader("📋 Dados Filtrados")
    st.caption(f"{len(df_filtrado)} registros encontrados")

    colunas_exibir = [
        'Alerta', 'Data da Solicitação', 'Descrição', 'Fornecedor',
        'TIPO', 'Frota', 'Qtde. Solicitada', 'Qtde. Pendente',
        'Valor', 'OC', 'Status'
    ]
    colunas_exibir = [col for col in colunas_exibir if col in df_filtrado.columns]

    st.dataframe(df_filtrado[colunas_exibir])

    st.download_button(
        label="📥 Baixar CSV filtrado",
        data=df_filtrado.to_csv(index=False).encode('utf-8'),
        file_name="dados_filtrados.csv",
        mime="text/csv"
    )

with aba4:
    st.subheader("💰 Gastos por Tipo")
    if 'Valor' in df_filtrado.columns:
        gastos_por_tipo = df_filtrado.groupby('TIPO')['Valor'].sum().reset_index()
        fig_tipo_gasto = px.bar(gastos_por_tipo.sort_values(by='Valor', ascending=False),
                                x='TIPO', y='Valor',
                                title='💰 Total de Gastos por Tipo', text_auto=True)
        st.plotly_chart(fig_tipo_gasto)

        st.subheader("💰 Gastos por Fornecedor")
        gastos_por_fornecedor = df_filtrado.groupby('Fornecedor')['Valor'].sum().reset_index()
        fig_fornecedor_gasto = px.bar(gastos_por_fornecedor.sort_values(by='Valor', ascending=False),
                                      x='Fornecedor', y='Valor',
                                      title='🏷️ Gastos por Fornecedor', text_auto=True)
        st.plotly_chart(fig_fornecedor_gasto)

            if 'Frota' in df_filtrado.columns:
            st.subheader("🚗 Gastos por Frota")
            gastos_por_frota = df_filtrado.groupby('Frota')['Valor'].sum().reset_index()
            fig_frota_gasto = px.bar(
                gastos_por_frota.sort_values(by='Valor', ascending=False),
                x='Frota', y='Valor',
                title='🚗 Gastos por Frota',
                text_auto=True
            )
            st.plotly_chart(fig_frota_gasto)

