import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_aggrid import AgGrid, GridOptionsBuilder
from datetime import datetime

# 1. Configurações Iniciais e Tema
st.set_page_config(
    page_title="Dashboard Follow-Up",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Cores da marca (exemplo)
PRIMARY_COLOR = "#1f77b4"
ALERT_COLOR = "#d62728"

# 2. Funções de Carregamento e Transformação (com cache)
@st.cache_data(ttl=3600)
def load_data(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path, parse_dates=["data_solicitacao", "data_entrega"])
    df["dias_em_situacao"] = (pd.Timestamp.today() - df["data_solicitacao"]).dt.days
    df["atendido_pct"] = 1 - (df["pendentes"] / df["solicitados"])
    return df

@st.cache_data(ttl=3600)
def preprocess(df: pd.DataFrame, freq: str, date_range: tuple):
    d0, d1 = date_range
    dff = df[(df["data_solicitacao"] >= d0) & (df["data_solicitacao"] <= d1)].copy()
    dff["periodo"] = dff["data_solicitacao"].dt.to_period(freq).dt.to_timestamp()
    return dff

# 3. Dados de Exemplo
DATA_PATH = "dados_followup.csv"
df = load_data(DATA_PATH)

# 4. Filtros de Data e Segmentação
st.sidebar.header("Segmentação Temporal")
freq = st.sidebar.radio("Agregação", options=["D", "W", "M"], format_func=lambda x: {"D":"Diária","W":"Semanal","M":"Mensal"}[x])
dmin, dmax = df["data_solicitacao"].min(), df["data_solicitacao"].max()
date_range = st.sidebar.slider("Período", min_value=dmin, max_value=dmax, value=(dmin, dmax), format="DD/MM/YYYY")

df_seg = preprocess(df, freq, date_range)

# 5. Cálculo de KPIs e Deltas
hoje = df_seg["periodo"].max()
anterior = hoje - pd.to_timedelta(1, unit=freq)
kpi_hoje = df_seg[df_seg["periodo"] == hoje].agg({"solicitados":"sum","pendentes":"sum","atendido_pct":"mean"})
kpi_ant = df_seg[df_seg["periodo"] == anterior].agg({"solicitados":"sum","pendentes":"sum","atendido_pct":"mean"})
delta_solic = kpi_hoje["solicitados"] - kpi_ant["solicitados"]
delta_atend = kpi_hoje["atendido_pct"] - kpi_ant["atendido_pct"]

# 6. Exibição de KPIs no Topo
col1, col2, col3 = st.columns([1,1,1])
with col1:
    st.metric("Solicitados", int(kpi_hoje["solicitados"]), delta=int(delta_solic))
with col2:
    delta_pct = f"{delta_atend:.1%}"
    st.metric("Atendido", f"{kpi_hoje['atendido_pct']:.1%}", delta=delta_pct)
with col3:
    pend_pct = df_seg["pendentes"].sum() / df_seg["solicitados"].sum()
    st.metric("Pendentes", f"{pend_pct:.1%}")

# 7. Alertas Flash
if pend_pct > 0.2:
    st.warning(f"Atenção: {pend_pct:.1%} dos pedidos estão pendentes, acima do threshold de 20%")

# 8. Narrativa e Contexto
st.markdown("""
Bem-vindo ao dashboard de follow-up. Aqui você visualiza em tempo real:
- Solicitados x Atendidos
- Tendência de atrasos
- Correlações entre equipamentos e atrasos
Use os controles ao lado para filtrar período e granularidade.
""")

# 9. Gráficos Avançados
# 9.1 Heatmap de Correlação
corr = df_seg[["tipo_equipamento","dias_em_situacao"]].groupby("tipo_equipamento").mean().reset_index()
fig_heat = px.density_heatmap(
    df_seg, x="tipo_equipamento", y="dias_em_situacao",
    color_continuous_scale="Blues"
)
fig_heat.update_layout(title="Heatmap: Tipo de Equipamento vs Dias em Situação")
st.plotly_chart(fig_heat, use_container_width=True)

# 9.2 Gráfico de Controle (Control Chart)
chart_data = df_seg.groupby("periodo")["dias_em_situacao"].mean().reset_index()
fig_ctrl = go.Figure()
fig_ctrl.add_trace(go.Scatter(x=chart_data["periodo"], y=chart_data["dias_em_situacao"],
                              mode="markers+lines", name="Média Dias"))
u_cl = chart_data["dias_em_situacao"].mean() + 3*chart_data["dias_em_situacao"].std()
l_cl = chart_data["dias_em_situacao"].mean() - 3*chart_data["dias_em_situacao"].std()
fig_ctrl.add_hline(y=u_cl, line_dash="dash", line_color=ALERT_COLOR, annotation_text="UCL")
fig_ctrl.add_hline(y=l_cl, line_dash="dash", line_color="green", annotation_text="LCL")
fig_ctrl.update_layout(title="Gráfico de Controle: Dias em Situação", xaxis_title="Período", yaxis_title="Dias")
st.plotly_chart(fig_ctrl, use_container_width=True)

# 9.3 Gauge de SLA
sla_pct = (df["dias_em_situacao"] <= 7).mean()
fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value=sla_pct*100,
    delta={'reference': 80, 'suffix': "%"},
    gauge={'axis': {'range': [0,100]},
           'bar': {'color': PRIMARY_COLOR},
           'steps': [
               {'range': [0, 80], 'color': "lightgray"},
               {'range': [80, 100], 'color': "lightgreen"}]},
    title={'text': "SLA (<7 dias)"}
))
st.plotly_chart(fig_gauge, use_container_width=True)

# 10. Drill-Down Dinâmico
st.markdown("### Atrasos por Tipo de Equipamento (Clique para filtrar tabela)")
fig_bar = px.bar(chart_data, x="periodo", y="dias_em_situacao",
                 labels={"dias_em_situacao":"Dias Médios","periodo":"Período"})
bar = st.plotly_chart(fig_bar, use_container_width=True)
# Captura clickData
clicked = st.session_state.get("clickData", None)
if bar and bar.json:
    st.session_state["clickData"] = bar.json.get("clickData")

# 11. Tabela Interativa
df_table = df_seg.copy()
if clicked:
    periodo_clicado = clicked["points"][0]["x"]
    df_table = df_table[df_table["periodo"] == periodo_clicado]

gb = GridOptionsBuilder.from_dataframe(df_table)
gb.configure_pagination()
gb.configure_default_column(editable=False, groupable=True, filter=True, sortable=True)
gb.configure_side_bar()
grid = AgGrid(df_table, gb.build(), enable_enterprise_modules=False)

# 12. Botões de Ação e Atualização de Status
with st.expander("Ações em Massa"):
    sel = grid["selected_rows"]
    if sel:
        st.button("Marcar como em revisão", on_click=lambda: print("Revisão marcada!"))
        st.button("Marcar como concluído", on_click=lambda: print("Concluído!"))

# 13. Integração com Slack (Exemplo)
def send_slack(msg: str):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if webhook:
        import requests
        requests.post(webhook, json={"text": msg})

if pend_pct > 0.2:
    send_slack(f"Alerta: {pend_pct:.1%} de pedidos pendentes no dashboard de follow-up.")

# Fim do Dashboard
