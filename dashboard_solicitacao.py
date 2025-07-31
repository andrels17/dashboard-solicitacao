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

# 📋 Validação no sidebar
st.sidebar.subheader("🔎 Validação do CSV")
st.sidebar.write(f"Separador detectado: `{sep}`")
st.sidebar.write(f"Colunas esperadas: {n_colunas}")
st.sidebar.write(f"✔️ Linhas válidas: {len(linhas_validas)}")
st.sidebar.write(f"❌ Linhas com erro: {len(linhas_invalidas)}")
if linhas_invalidas:
    with st.expander("Ver linhas com erro"):
        for i, linha in linhas_invalidas[:10]:
            st.write(f"Linha {i}: {linha}")

# 📈 Carregamento dos dados
df = pd.read_csv(arquivo_limpo, sep=sep, encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)
df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

# 💰 Cálculo do valor total
if 'Qtd.' in df.columns and 'Valor Último' in df.columns:
    df['Valor'] = df['Qtd.'] * df['Valor Último']

# 🎛️ Filtros
st.title("📊 Dashboard de Equipamentos")
tipos = sorted(df['TIPO'].dropna().unique()) if 'TIPO' in df.columns else []
fornecedores = sorted(df['Fornecedor'].dropna().unique()) if 'Fornecedor' in df.columns else []
frotas = sorted(df['Frota'].dropna().unique()) if 'Frota' in df.columns else []
data_min = df['Data'].min()
data_max = df['Data'].max()

with st.sidebar:
    st.header("🎛️ Filtros")
    tipo_selecionado = st.selectbox("Tipo", ["Todos"] + tipos)
    fornecedor_selecionado = st.selectbox("Fornecedor", ["Todos"] + fornecedores) if fornecedores else "Todos"
    frota_selecionada = st.selectbox("Frota", ["Todos"] + frotas) if frotas else "Todos"
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])

# 🔍 Aplicação dos filtros
filtro = (
    (df['Data'] >= pd.to_datetime(data_inicio)) &
    (df['Data'] <= pd.to_datetime(data_fim))
)
if tipo_selecionado != "Todos":
    filtro &= (df['TIPO'] == tipo_selecionado)
if fornecedor_selecionado != "Todos":
    filtro &= (df['Fornecedor'] == fornecedor_selecionado)
if frota_selecionada != "Todos":
    filtro &= (df['Frota'] == frota_selecionada)

df_filtrado = df[filtro].copy()
df_filtrado['AnoMes'] = df_filtrado['Data'].dt.to_period("M").astype(str)

# 📚 Abas
aba1, aba2, aba3, aba4 = st.tabs(["📍 Indicadores", "📊 Pendências", "📋 Tabela", "💰 Gastos"])

with aba1:
    st.subheader("📍 Indicadores")
    if 'Qtd. Solicitada' in df_filtrado.columns:
        st.metric("Solicitado", int(df_filtrado['Qtd. Solicitada'].sum()))
    if 'Qtd. Pendente' in df_filtrado.columns:
        st.metric("Pendente", int(df_filtrado['Qtd. Pendente'].sum()))
    if 'Valor' in df_filtrado.columns:
        st.metric("Valor Total", f"R$ {df_filtrado['Valor'].sum():,.2f}")

with aba2:
    st.subheader("📊 Pendências")

    if 'Status' in df_filtrado.columns:
        fig_status = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
        st.plotly_chart(fig_status)

    if 'Qtd. Pendente' in df_filtrado.columns:
        pendencia_mes = df_filtrado.groupby('AnoMes')['Qtd. Pendente'].sum().reset_index()
        fig_mes = px.line(pendencia_mes, x='AnoMes', y='Qtd. Pendente', markers=True, title='📅 Pendência Mensal')
        st.plotly_chart(fig_mes)

        if 'Fornecedor' in df_filtrado.columns:
            pendencia_fornecedor = df_filtrado.groupby('Fornecedor')['Qtd. Pendente'].sum().reset_index()
            fig_fornecedor = px.bar(
                pendencia_fornecedor.sort_values(by='Qtd. Pendente', ascending=False),
                x='Qtd. Pendente', y='Fornecedor', orientation='h',
                title='📦 Pendência por Fornecedor',
                text_auto=True
            )
            st.plotly_chart(fig_fornecedor)

with aba3:
    st.subheader("📋 Dados Filtrados")
    st.caption(f"{len(df_filtrado)} registros encontrados")

    st.dataframe(df_filtrado)

    st.download_button(
        label="📥 Baixar CSV filtrado",
        data=df_filtrado.to_csv(index=False).encode('utf-8'),
        file_name="dados_filtrados.csv",
        mime="text/csv"
    )

with aba4:
    st.subheader("💰 Gastos")

    if 'Valor' in df_filtrado.columns:
        if 'TIPO' in df_filtrado.columns:
            gastos_por_tipo = df_filtrado.groupby('TIPO')['Valor'].sum().reset_index()
            fig_tipo = px.bar(gastos_por_tipo.sort_values(by='Valor', ascending=False),
                              x='TIPO', y='Valor',
                              title='💰 Gastos por Tipo', text_auto=True)
            st.plotly_chart(fig_tipo)

        if 'Fornecedor' in df_filtrado.columns:
            gastos_por_fornecedor = df_filtrado.groupby('Fornecedor')['Valor'].sum().reset_index()
            fig_forn = px.bar(gastos_por_fornecedor.sort_values(by='Valor', ascending=False),
                              x='Fornecedor', y='Valor',
                              title='🏷️ Gastos por Fornecedor', text_auto=True)
            st.plotly_chart(fig_forn)

        if 'Frota' in df_filtrado.columns:
            gastos_por_frota = df_filtrado.groupby('Frota')['Valor'].sum().reset_index()
            fig_frota = px.bar(gastos_por_frota.sort_values(by='Valor', ascending=False),
                               x='Frota', y='Valor',
                               title='🚗 Gastos por Frota', text_auto=True)
            st.plotly_chart(fig_frota)
