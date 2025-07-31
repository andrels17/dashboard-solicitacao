import streamlit as st
import pandas as pd
import plotly.express as px
import csv

# 🔍 Funções para validação do CSV
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

# 📋 Sidebar: relatório da validação
st.sidebar.subheader("🔎 Validação do CSV")
st.sidebar.write(f"Separador detectado: `{sep}`")
st.sidebar.write(f"Colunas esperadas: {n_colunas}")
st.sidebar.write(f"✔️ Linhas válidas: {len(linhas_validas)}")
st.sidebar.write(f"❌ Linhas com erro: {len(linhas_invalidas)}")
if linhas_invalidas:
    with st.expander("Ver linhas com erro"):
        for i, linha in linhas_invalidas[:10]:
            st.write(f"Linha {i}: {linha}")

# 📈 Carregamento de dados
df = pd.read_csv(arquivo_limpo, sep=sep, encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df = df.dropna(subset=['Mês', 'TIPO', 'Data da Solicitação'])

# 💰 Gera coluna "Valor" se houver colunas específicas
if all(col in df.columns for col in ['Combustível', 'Manutenção', 'Peças']):
    df['Valor'] = df[['Combustível', 'Manutenção', 'Peças']].sum(axis=1)

# 🎛️ Filtros
st.title("📊 Dashboard de Solicitações TO")
meses = sorted(df['Mês'].dropna().unique())
tipos = sorted(df['TIPO'].dropna().unique())
fornecedores = sorted(df['Fornecedor'].dropna().unique())
departamentos = sorted(df['Departamento'].dropna().unique()) if 'Departamento' in df.columns else []
frotas = sorted(df['Frota'].dropna().unique()) if 'Frota' in df.columns else []
data_min = df['Data da Solicitação'].min()
data_max = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("🎛️ Filtros")
    mes = st.selectbox("Mês", meses)
    tipo = st.selectbox("Tipo", tipos)
    fornecedor = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    selected_departamentos = st.multiselect("Departamento", ["Todos"] + departamentos, default=["Todos"])
    selected_frota = st.selectbox("Frota", ["Todos"] + frotas) if frotas else "Todos"
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])

# 🔍 Aplicação dos filtros
filtro = (
    (df['Mês'] == mes) &
    (df['TIPO'] == tipo) &
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if fornecedor != "Todos":
    filtro &= (df['Fornecedor'] == fornecedor)
if "Todos" not in selected_departamentos:
    filtro &= df['Departamento'].isin(selected_departamentos)
if selected_frota != "Todos":
    filtro &= (df['Frota'] == selected_frota)

df_filtrado = df[filtro].copy().sort_values(by='Qtde. Pendente', ascending=False)
df_filtrado['Alerta'] = df_filtrado['Qtde. Pendente'].apply(lambda x: '⚠️' if x > 50 else '')

# 📚 Abas do dashboard
aba1, aba2, aba3 = st.tabs(["📍 Indicadores", "📊 Gráficos", "📋 Tabela"])

with aba1:
    st.subheader("📍 Indicadores")
    st.metric("Solicitado", f"{int(df_filtrado['Qtde. Solicitada'].sum()):,}")
    st.metric("Entregue", f"{int(df_filtrado['Qtde. Entregue'].sum()):,}")
    st.metric("Pendente", f"{int(df_filtrado['Qtde. Pendente'].sum()):,}")
    st.metric("% com OC", f"{(df_filtrado['OC'] == 'Tem OC').mean() * 100:.1f}%")
    if 'Valor' in df_filtrado.columns:
        st.metric("Gasto Total", f"R$ {df_filtrado['Valor'].sum():,.2f}")

with aba2:
    st.subheader("📊 Visualizações")

    fig1 = px.bar(df_filtrado.groupby('Descrição')['Qtde. Pendente'].sum().nlargest(10).reset_index(),
                  x='Qtde. Pendente', y='Descrição', orientation='h', title='Top 10 Pendentes')
    st.plotly_chart(fig1)

    fig2 = px.pie(df_filtrado, names='Status', title='Distribuição por Status')
    st.plotly_chart(fig2)

    df_trend = df_filtrado.copy()
    df_trend['AnoMes'] = df_trend['Data da Solicitação'].dt.to_period("M").astype(str)
    fig3 = px.line(df_trend.groupby('AnoMes')['Qtde. Pendente'].sum().reset_index(),
                   x='AnoMes', y='Qtde. Pendente', markers=True, title='Pendências por Mês')
    st.plotly_chart(fig3)

    fig4 = px.scatter(df_filtrado.groupby('Fornecedor')['Qtde. Pendente'].sum().reset_index(),
                      x='Fornecedor', y='Qtde. Pendente', size='Qtde. Pendente', title='Pendência por Fornecedor')
    st.plotly_chart(fig4)

    if 'Valor' in df_filtrado.columns and 'Frota' in df_filtrado.columns:
        gastos_por_frota = df_filtrado.groupby('Frota')['Valor'].sum().reset_index().sort_values(by='Valor', ascending=False)
        fig_gastos = px.bar(gastos_por_frota, x='Frota', y='Valor', title='💰 Gastos por Frota')
        st.plotly_chart(fig_gastos)

    if "Todos" in selected_departamentos:
        st.subheader("📊 Comparativo entre Departamentos")

        pendencias_por_dep = df_filtrado.groupby('Departamento')['Qtde. Pendente'].sum().reset_index()
        fig_pend_dep = px.bar(pendencias_por_dep.sort_values(by='Qtde. Pendente', ascending=False),
                              x='Departamento', y='Qtde. Pendente',
                              title='📍 Pendências por Departamento', text_auto=True)
        st.plotly_chart(fig_pend_dep)

        if 'Valor' in df_filtrado.columns:
            gastos_por_dep = df_filtrado.groupby('Departamento')['Valor'].sum().reset_index()
            fig_gasto_dep = px.bar(gastos_por_dep.sort_values(by='Valor', ascending=False),
                                   x='Departamento', y='Valor',
                                   title='💰 Gastos por Departamento', text_auto=True)
            st.plotly_chart(fig_gasto_dep)
            
    with aba3:
    st.subheader("📋 Dados Filtrados")
    st.caption(f"{len(df_filtrado)} registros encontrados")

    colunas_exibir = [
        'Alerta', 'Data da Solicitação', 'Descrição', 'Fornecedor',
        'Departamento', 'Frota', 'Qtde. Solicitada', 'Qtde. Pendente',
        'Valor', 'OC', 'Status'
    ]
    colunas_exibir = [col for col in colunas_exibir if col in df_filtrado.columns]

    st.dataframe(df_filtrado[colunas_exibir])

    # 📥 Botão de download
    st.download_button(
        label="📥 Baixar CSV filtrado",
        data=df_filtrado.to_csv(index=False).encode('utf-8'),
        file_name="dados_filtrados.csv",
        mime="text/csv"
    )

