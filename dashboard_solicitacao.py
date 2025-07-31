import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode

# 📁 Arquivo CSV
arquivo_original = "solicitacao_to.csv"
arquivo_limpo = "csv_validado.csv"

# 🔍 Detecta separador e estrutura
def detectar_configuracao_csv(arquivo):
    with open(arquivo, "r", encoding="utf-8") as f:
        linha = f.readline()
        sep = ";" if ";" in linha else "," if "," in linha else ","
        n_colunas = len(linha.strip().split(sep))
    return sep, n_colunas

# 🧼 Valida estrutura e grava versão limpa
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

sep, n_colunas, linhas_validas, linhas_invalidas = validar_csv(arquivo_original, arquivo_limpo)

# 🎨 Layout
st.set_page_config(page_title="Dashboard de Solicitações", layout="wide")
st.title("📊 Dashboard de Equipamentos")
st.sidebar.subheader("📎 Relatório do CSV")
st.sidebar.write(f"Separador detectado: `{sep}`")
st.sidebar.write(f"Nº de colunas: {n_colunas}")
st.sidebar.write(f"✔️ Linhas válidas: {len(linhas_validas)}")
st.sidebar.write(f"❌ Linhas inválidas: {len(linhas_invalidas)}")
st.sidebar.markdown("🌙 Dica: use extensão como [Dark Reader](https://darkreader.org/) para modo escuro.")

# 📊 Dados
df = pd.read_csv(arquivo_limpo, sep=sep, encoding="utf-8")
df.rename(columns={col: col.strip() for col in df.columns}, inplace=True)

# 🔧 Renomeia 'Qtd.' e 'Valor Último'
for col in df.columns:
    col_limpo = unidecode.unidecode(col.lower().replace(" ", "").replace(".", ""))
    if "qtde" in col_limpo or "qtd" in col_limpo:
        df.rename(columns={col: "Qtd."}, inplace=True)
    if "valorultimacompra" in col_limpo or "valoru" in col_limpo or "ultimovalor" in col_limpo:
        df.rename(columns={col: "Valor Último"}, inplace=True)

# 📆 Datas
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df['AnoMes'] = df['Data da Solicitação'].dt.to_period("M").astype(str)

# 💰 Valor
try:
    df['Qtd.'] = pd.to_numeric(df['Qtd.'], errors='coerce')
    df['Valor Último'] = pd.to_numeric(df['Valor Último'], errors='coerce')
    df['Valor'] = df['Qtd.'] * df['Valor Último']
except Exception as e:
    st.sidebar.error(f"Erro ao calcular coluna 'Valor': {e}")

# ⚠️ Alerta de dias em situação
if 'Dias em Situação' in df.columns:
    df['Alerta Dias'] = pd.to_numeric(df['Dias em Situação'], errors='coerce').apply(lambda x: '⚠️' if x >= 30 else '')

# 🎛️ Filtros
tipos = sorted(df['TIPO'].dropna().unique()) if 'TIPO' in df.columns else []
fornecedores = sorted(df['Fornecedor'].dropna().unique()) if 'Fornecedor' in df.columns else []
frotas = sorted(df['Frota'].dropna().unique()) if 'Frota' in df.columns else []
data_min = df['Data da Solicitação'].min()
data_max = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("🎛️ Filtros")
    tipo = st.selectbox("Tipo", ["Todos"] + tipos)
    fornecedor = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    frota = st.selectbox("Frota", ["Todos"] + frotas)
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])
    st.write(f"📅 Intervalo detectado: {data_min.date()} → {data_max.date()}")

# 🔍 Aplica filtros
filtro = (
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if tipo != "Todos": filtro &= (df['TIPO'] == tipo)
if fornecedor != "Todos": filtro &= (df['Fornecedor'] == fornecedor)
if frota != "Todos": filtro &= (df['Frota'] == frota)

df_filtrado = df[filtro].copy()
st.sidebar.write(f"🔎 Registros filtrados: {len(df_filtrado)}")

# 💾 Exporta CSV filtrado
csv_export = df_filtrado.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Baixar Dados Filtrados (CSV)",
    data=csv_export,
    file_name="dados_filtrados.csv",
    mime="text/csv"
)

# 📚 Abas
aba1, aba2, aba3 = st.tabs(["📍 Indicadores", "📊 Gráficos", "💰 Gastos"])

# 🔢 Indicadores
with aba1:
    st.subheader("📍 Indicadores")

    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros.")
    else:
        qtd_solicitada = df_filtrado['Qtd.'].sum()
        qtd_solicitada = 0 if pd.isna(qtd_solicitada) else int(qtd_solicitada)
        st.metric("📦 Solicitado", qtd_solicitada)

        if 'Qtd. Pendente' in df_filtrado.columns:
            qtd_pendente = df_filtrado['Qtd. Pendente'].sum()
            qtd_pendente = 0 if pd.isna(qtd_pendente) else int(qtd_pendente)
            st.metric("⏳ Pendente", qtd_pendente)

        if 'Valor' in df_filtrado.columns:
            valor_total = df_filtrado['Valor'].sum()
            valor_total = 0.0 if pd.isna(valor_total) else valor_total
            st.metric("💸 Valor Total", f"R$ {valor_total:,.2f}")

        if 'Dias em Situação' in df_filtrado.columns:
            media_dias = df_filtrado['Dias em Situação'].mean()
            media_dias = 0.0 if pd.isna(media_dias) else media_dias
            st.metric("📅 Média Dias", f"{media_dias:.1f} dias")

# 📊 Gráficos
with aba2:
    st.subheader("📊 Gráficos")
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado para gráficos.")
    else:
        if 'AnoMes' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            valor_mensal = df_filtrado.groupby('AnoMes')['Valor'].sum().reset_index()
            fig_valor_mes = px.line(valor_mensal, x='AnoMes', y='Valor', markers=True, title='📈 Valor por Mês')
            st.plotly_chart(fig_valor_mes, use_container_width=True)

        if 'Fornecedor' in df_filtrado.columns and 'Qtd. Pendente' in df_filtrado.columns:
            pend = df_filtrado.groupby('Fornecedor')['Qtd. Pendente'].sum().reset_index()
            fig_forn = px.bar(pend.sort_values(by='Qtd. Pendente', ascending=False),
                              x='Qtd. Pendente', y='Fornecedor',
                              orientation='h',
                              title='📦 Pendência por Fornecedor',
                              text_auto=True,
                              color='Qtd. Pendente',
                              color_continuous_scale='Oranges')
            st.plotly_chart(fig_forn, use_container_width=True)

        if 'TIPO' in df_filtrado.columns and 'Qtd.' in df_filtrado.columns:
            tipo_qtd = df_filtrado.groupby('TIPO')['Qtd.'].sum().reset_index()
            fig_tipo = px.bar(tipo_qtd.sort_values(by='Qtd.', ascending=False),
                              x='TIPO', y='Qtd.',
                              title='🧱 Quantidade por Tipo',
                              text_auto=True,
                              color='Qtd.',
                              color_continuous_scale='Purples')
            st.plotly_chart(fig_tipo, use_container_width=True)

# 💰 Gastos
with aba3:
    st.subheader("💰 Gastos")
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado para exibir os gastos.")
    else:
        # 💸 Gastos por Tipo
        if 'TIPO' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            gasto_tipo = df_filtrado.groupby('TIPO')['Valor'].sum().reset_index()
            gasto_tipo['Valor'] = gasto_tipo['Valor'].fillna(0)
            fig_gt = px.bar(gasto_tipo.sort_values(by='Valor', ascending=False),
                            x='TIPO', y='Valor',
                            title='💰 Gastos por Tipo',
                            text_auto=True,
                            color='Valor',
                            color_continuous_scale='Teal')
            st.plotly_chart(fig_gt, use_container_width=True)

            fig_pizza_tipo = px.pie(gasto_tipo,
                                    names='TIPO',
                                    values='Valor',
                                    title='🧁 Distribuição de Gastos por Tipo')
            st.plotly_chart(fig_pizza_tipo, use_container_width=True)

        # 🏢 Gastos por Fornecedor
        if 'Fornecedor' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            gasto_forn = df_filtrado.groupby('Fornecedor')['Valor'].sum().reset_index()
            gasto_forn['Valor'] = gasto_forn['Valor'].fillna(0)
            fig_forn_gasto = px.bar(gasto_forn.sort_values(by='Valor', ascending=False),
                                    x='Fornecedor', y='Valor',
                                    title='🏢 Gastos por Fornecedor',
                                    text_auto=True,
                                    color='Valor',
                                    color_continuous_scale='Blues')
            st.plotly_chart(fig_forn_gasto, use_container_width=True)
