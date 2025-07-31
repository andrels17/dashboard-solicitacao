import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import unidecode

# 📁 Arquivo CSV
arquivo_original = "solicitacao_to.csv"
arquivo_limpo    = "csv_validado.csv"

# 🔍 Detecta separador e estrutura
def detectar_configuracao_csv(arquivo):
    with open(arquivo, "r", encoding="utf-8") as f:
        primeira = f.readline()
        sep = ";" if ";" in primeira else "," if "," in primeira else ","
        n_colunas = len(primeira.strip().split(sep))
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

# 🔧 Mapeia e renomeia colunas de quantidade e valor
rename_map = {}
for col in df.columns:
    chave = unidecode.unidecode(col.lower().replace(" ", "").replace(".", ""))
    if chave in ("qtde", "qtd", "quantidade"):
        rename_map[col] = "Qtd. Solicitada"
    elif "qtdpendente" in chave or "quantidadependente" in chave:
        rename_map[col] = "Qtd. Pendente"
    elif "valorultimacompra" in chave or "valoru" in chave or "ultimovalor" in chave:
        rename_map[col] = "Valor Último"

df.rename(columns=rename_map, inplace=True)

# 📆 Datas
df['Data da Solicitação'] = pd.to_datetime(df['Data da Solicitação'], errors='coerce')
df['AnoMes'] = df['Data da Solicitação'].dt.to_period("M").astype(str)

# 💰 Cálculo de Valor
try:
    df['Qtd. Solicitada']   = pd.to_numeric(df['Qtd. Solicitada'], errors='coerce')
    df['Valor Último']      = pd.to_numeric(df['Valor Último'], errors='coerce')
    df['Valor']             = df['Qtd. Solicitada'] * df['Valor Último']
except Exception as e:
    st.sidebar.error(f"Erro ao calcular coluna 'Valor': {e}")

# ⚠️ Alerta de dias em situação
if 'Dias em Situação' in df.columns:
    df['Dias em Situação'] = pd.to_numeric(df['Dias em Situação'], errors='coerce')
    df['Alerta Dias']      = df['Dias em Situação'].apply(lambda x: '⚠️' if x >= 30 else '')

# 🎛️ Filtros
tipos        = sorted(df['TIPO'].dropna().unique())        if 'TIPO' in df.columns        else []
fornecedores = sorted(df['Fornecedor'].dropna().unique()) if 'Fornecedor' in df.columns else []
frotas       = sorted(df['Frota'].dropna().unique())      if 'Frota' in df.columns       else []
data_min     = df['Data da Solicitação'].min()
data_max     = df['Data da Solicitação'].max()

with st.sidebar:
    st.header("🎛️ Filtros")
    tipo     = st.selectbox("Tipo",        ["Todos"] + tipos)
    fornecedor = st.selectbox("Fornecedor", ["Todos"] + fornecedores)
    frota    = st.selectbox("Frota",        ["Todos"] + frotas)
    data_inicio, data_fim = st.date_input("Período", [data_min, data_max])
    st.write(f"📅 Intervalo detectado: {data_min.date()} → {data_max.date()}")

# 🔍 Aplica filtros
filtro = (
    (df['Data da Solicitação'] >= pd.to_datetime(data_inicio)) &
    (df['Data da Solicitação'] <= pd.to_datetime(data_fim))
)
if tipo != "Todos":      filtro &= (df['TIPO'] == tipo)
if fornecedor != "Todos": filtro &= (df['Fornecedor'] == fornecedor)
if frota != "Todos":     filtro &= (df['Frota'] == frota)

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
        # 📦 Qtd. Solicitada
        try:
            qs = df_filtrado['Qtd. Solicitada'].sum()
            qs = int(qs) if pd.notnull(qs) else 0
            st.metric("📦 Solicitada", qs)
        except:
            st.metric("📦 Solicitada", 0)

        # ⏳ Qtd. Pendente
        if 'Qtd. Pendente' in df_filtrado.columns:
            try:
                qp = df_filtrado['Qtd. Pendente'].sum()
                qp = int(qp) if pd.notnull(qp) else 0
                st.metric("⏳ Pendente", qp)
            except:
                st.metric("⏳ Pendente", 0)

        # 💸 Valor Total
        if 'Valor' in df_filtrado.columns:
            try:
                vt = df_filtrado['Valor'].sum()
                vt = 0.0 if pd.isna(vt) else vt
                st.metric("💸 Valor Total", f"R$ {vt:,.2f}")
            except:
                st.metric("💸 Valor Total", "R$ 0,00")

        # 📅 Média Dias em Situação
        if 'Dias em Situação' in df_filtrado.columns:
            try:
                md = df_filtrado['Dias em Situação'].mean()
                md = 0.0 if pd.isna(md) else md
                st.metric("📅 Média Dias", f"{md:.1f} dias")
            except:
                st.metric("📅 Média Dias", "0,0 dias")

# 📊 Gráficos
with aba2:
    st.subheader("📊 Gráficos")
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado para gráficos.")
    else:
        # Valor por Mês
        if 'AnoMes' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            valor_mensal = df_filtrado.groupby('AnoMes')['Valor'].sum().reset_index()
            fig1 = px.line(valor_mensal, x='AnoMes', y='Valor',
                           markers=True, title='📈 Valor por Mês')
            st.plotly_chart(fig1, use_container_width=True)

        # Pendência por Fornecedor
        if 'Fornecedor' in df_filtrado.columns and 'Qtd. Pendente' in df_filtrado.columns:
            pend = df_filtrado.groupby('Fornecedor')['Qtd. Pendente'].sum().reset_index()
            fig2 = px.bar(pend.sort_values(by='Qtd. Pendente', ascending=False),
                          x='Qtd. Pendente', y='Fornecedor',
                          orientation='h',
                          title='📦 Pendência por Fornecedor',
                          text_auto=True, color='Qtd. Pendente',
                          color_continuous_scale='Oranges')
            st.plotly_chart(fig2, use_container_width=True)

        # Quantidade por Tipo
        if 'TIPO' in df_filtrado.columns and 'Qtd. Solicitada' in df_filtrado.columns:
            tipo_qtd = df_filtrado.groupby('TIPO')['Qtd. Solicitada'].sum().reset_index()
            fig3 = px.bar(tipo_qtd.sort_values(by='Qtd. Solicitada', ascending=False),
                          x='TIPO', y='Qtd. Solicitada',
                          title='🧱 Quantidade por Tipo',
                          text_auto=True, color='Qtd. Solicitada',
                          color_continuous_scale='Purples')
            st.plotly_chart(fig3, use_container_width=True)

# 💰 Gastos
with aba3:
    st.subheader("💰 Gastos")

    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado para exibir os gastos.")
    else:
        # Gastos por Tipo
        if 'TIPO' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            gasto_tipo = df_filtrado.groupby('TIPO')['Valor'].sum().reset_index()
            gasto_tipo['Valor'] = gasto_tipo['Valor'].fillna(0)
            fig4 = px.bar(gasto_tipo.sort_values(by='Valor', ascending=False),
                          x='TIPO', y='Valor',
                          title='💰 Gastos por Tipo',
                          text_auto=True, color='Valor',
                          color_continuous_scale='Teal')
            st.plotly_chart(fig4, use_container_width=True)

            fig5 = px.pie(gasto_tipo, names='TIPO', values='Valor',
                          title='🧁 Distribuição de Gastos por Tipo')
            st.plotly_chart(fig5, use_container_width=True)

        # Gastos por Fornecedor
        if 'Fornecedor' in df_filtrado.columns and 'Valor' in df_filtrado.columns:
            gasto_forn = df_filtrado.groupby('Fornecedor')['Valor'].sum().reset_index()
            gasto_forn['Valor'] = gasto_forn['Valor'].fillna(0)
            fig6 = px.bar(gasto_forn.sort_values(by='Valor', ascending=False),
                          x='Fornecedor', y='Valor',
                          title='🏢 Gastos por Fornecedor',
                          text_auto=True, color='Valor',
                          color_continuous_scale='Blues')
            st.plotly_chart(fig6, use_container_width=True)
```
