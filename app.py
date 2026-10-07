import os
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

# 1. CONFIGURAÇÕES DA PÁGINA WEB E AMBIENTE
st.set_page_config(page_title="Family Office - Painel Macro", layout="wide", page_icon="📊")
load_dotenv()

# No Render, utilizaremos as "Environment Variables" da própria plataforma
if not os.getenv("GROQ_API_KEY"):
    st.error("ERRO: GROQ_API_KEY não configurada no ambiente.")
    st.stop()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELO = "openai/gpt-oss-20b"

# 2. CONSULTA AOS DADOS OFICIAIS DO BANCO CENTRAL
def consultar_sgs_bacen(codigo_serie: int):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
    data_inicio = (datetime.now() - pd.DateOffset(months=15)).strftime("%d/%m/%Y")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    parametros = {
        "formato": "json",
        "dataInicial": data_inicio,
        "dataFinal": datetime.now().strftime("%d/%m/%Y"),
    }
    response = requests.get(url, params=parametros, headers=headers, timeout=15)
    response.raise_for_status()
    dados = response.json()
    if not isinstance(dados, list) or not dados:
        raise RuntimeError(f"O SGS não retornou observações para a série {codigo_serie}.")

    df = pd.DataFrame(dados)
    df["valor"] = pd.to_numeric(df["valor"], errors="raise")
    df["data"] = df["data"].astype(str)
    return df

# 3. INTERFACE GRÁFICA (UI) - CABEÇALHO
st.title("📊 Painel de Governança Macroeconômica")
st.markdown(f"**Consulta:** {datetime.now().strftime('%d/%m/%Y')} | **Ambiente:** Nuvem Cloud (Soberano)")
st.divider()

# Barra Lateral
st.sidebar.header("⚙️ Parâmetros Financeiros")
patrimonio_inicial = st.sidebar.number_input("Patrimônio Atual (R$)", value=860000.0, step=10000.0)
resgate_mensal = st.sidebar.number_input("Resgate Mensal Alvo (R$)", value=11000.0, step=1000.0)
reserva_saude = st.sidebar.number_input("Fundo de Saúde Isolado (R$)", value=45000.0, step=5000.0)

# Carga das séries oficiais: meta Selic anual e IPCA mensal.
try:
    df_selic = consultar_sgs_bacen(432)
    df_ipca = consultar_sgs_bacen(433)
except (requests.RequestException, ValueError, RuntimeError) as erro:
    st.error(f"Não foi possível consultar os dados oficiais do Banco Central: {erro}")
    st.stop()

selic_anual = df_selic["valor"].iloc[-1]
ipca_mensal = df_ipca["valor"].iloc[-1]
data_selic = df_selic["data"].iloc[-1]
data_ipca = df_ipca["data"].iloc[-1]

selic_projetada_por_ano = {
    2026: 13.50,
    2027: 12.00,
    2028: 10.50,
    2029: 10.00,
}
historico_tendencia_selic = {
    2026: "Expectativa de corte residual em relação aos 13,75% atuais.",
    2027: "Queda gradual mantida sob estabilidade há várias semanas.",
    2028: "Continuidade do ciclo de afrouxamento monetário.",
    2029: "Estabilização dos juros no patamar de dois dígitos.",
}

# Métricas Principais
col1, col2, col3 = st.columns(3)
col1.metric(
    "Meta Selic vigente (a.a.)",
    f"{selic_anual:.2f}%",
    help=f"SGS 432; observação de {data_selic}.",
)
col2.metric(
    "IPCA do último mês",
    f"{ipca_mensal:.2f}%",
    help=f"SGS 433; variação mensal referente a {data_ipca}.",
)
col3.metric("Fôlego Líquido de Consumo", f"R$ {patrimonio_inicial - reserva_saude:,.2f}", delta="Blindado")

st.divider()

# 4. PROJEÇÃO NOMINAL DE JUROS COMPOSTOS E CONSUMO
st.subheader("📈 Projeção Matemática de Juros Compostos vs Consumo")
st.markdown(
    "Projeção nominal de 36 meses, aplicando a premissa Selic de cada ano e convertendo-a "
    "para uma taxa mensal efetiva; "
    "o último IPCA mensal é mantido constante apenas como hipótese para reajustar as retiradas."
)
st.caption(
    f"A meta Selic vigente consultada no BCB é {selic_anual:.2f}% a.a.; "
    "as taxas abaixo são premissas de cenário, não dados observados nem projeção oficial do BCB."
)
st.dataframe(
    pd.DataFrame(
        [
            {
                "Ano": ano,
                "Selic projetada": f"{taxa:.2f}% a.a.",
                "Tendência do cenário": historico_tendencia_selic[ano],
            }
            for ano, taxa in selic_projetada_por_ano.items()
        ]
    ),
    hide_index=True,
    use_container_width=True,
)

# Projeção simplificada em valores nominais, antes de impostos e taxas.
meses = 36
saldo_projetado = []
datas_projetadas = pd.date_range(start=datetime.now(), periods=meses, freq="ME")
rotulos_datas_projetadas = datas_projetadas.strftime("%m/%Y").tolist()

taxas_selic_anuais_mensais = [
    selic_projetada_por_ano.get(data.year, selic_projetada_por_ano[2029])
    for data in datas_projetadas
]
taxas_juros_mensais = [
    (1 + taxa_anual / 100) ** (1 / 12) - 1
    for taxa_anual in taxas_selic_anuais_mensais
]
taxa_inflacao_mensal = ipca_mensal / 100
capital_atual = patrimonio_inicial - reserva_saude

for i, taxa_juros_mensal in enumerate(taxas_juros_mensais):
    # Rendimento sobre o saldo do período
    rendimento = capital_atual * taxa_juros_mensal
    # Reajusta as retiradas pelo último IPCA mensal observado.
    capital_atual = capital_atual + rendimento - (resgate_mensal * ((1 + taxa_inflacao_mensal) ** i))
    saldo_projetado.append(max(0.0, capital_atual))

# Renderização do Gráfico com Plotly
fig_projecao = go.Figure()
fig_projecao.add_trace(go.Scatter(x=rotulos_datas_projetadas, y=saldo_projetado, mode='lines+markers', name='Saldo Líquido Projetado', line=dict(color='#00FF00', width=4)))
fig_projecao.update_layout(
    title="Curva de Resiliência do Capital Principal (Tesouro Selic)",
    template="plotly_dark",
    xaxis_title="Linha do Tempo (Meses)",
    yaxis_title="Saldo Disponível (R$)",
    height=400
)
st.plotly_chart(fig_projecao, use_container_width=True)

st.divider()

# 5. INTEGRAÇÃO COM A INTELIGÊNCIA ARTIFICIAL (GROQ)
st.subheader("🤖 Auditoria Analítica via LPU Groq")

if st.button("🚀 Rodar Auditoria de Estresse Patrimonial"):
    taxas_selic_por_ano_texto = "; ".join(
        f"{ano}: {taxa:.2f}% a.a."
        for ano, taxa in selic_projetada_por_ano.items()
    )
    total_retiradas_projetadas = sum(
        resgate_mensal * ((1 + taxa_inflacao_mensal) ** mes)
        for mes in range(meses)
    )
    saldo_final_projetado = saldo_projetado[-1]
    contexto_dados = (
        f"BCB SGS 432: meta Selic vigente de {selic_anual:.2f}% a.a. em {data_selic}; "
        f"BCB SGS 433: IPCA de {data_ipca} = {ipca_mensal:.2f}% no mês; é inflação observada, não anual. "
        f"Premissas anuais da projeção (cenário informado): {taxas_selic_por_ano_texto}. "
        "Em cada mês, a taxa anual daquele ano é convertida pela fórmula (1 + taxa anual)^(1/12) - 1."
    )
    prompt_usuario = (
        f"Use estas unidades sem convertê-las incorretamente: {contexto_dados} "
        f"O capital investido inicial é R$ {patrimonio_inicial - reserva_saude:.2f}; "
        f"a reserva de saúde de R$ {reserva_saude:.2f} fica separada e intacta. "
        f"A retirada inicial é R$ {resgate_mensal:.2f} por mês, reajustada pelo último IPCA mensal "
        f"constante como hipótese durante {meses} meses. O cálculo determinístico do app resulta em "
        f"R$ {total_retiradas_projetadas:.2f} de retiradas acumuladas e saldo investido final de "
        f"R$ {saldo_final_projetado:.2f}; use esses valores sem recalculá-los. "
        "Produza Markdown conciso em português, identifique claramente taxas a.a. e a.m., "
        "formate valores no padrão brasileiro, por exemplo R$ 860.000,00, "
        "explique as limitações e não trate a projeção como garantia nem recomendação financeira."
    )
    
    with st.spinner("Conectando aos chips da Groq..."):
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Responda somente com conteúdo Markdown legível. Não inclua objetos da API, escapes Unicode ou tabelas extensas."},
                    {"role": "user", "content": prompt_usuario}
                ],
                model=MODELO,
                temperature=0.2,
                max_completion_tokens=4096
            )

            escolha = chat_completion.choices[0]
            texto = escolha.message.content
            if not texto:
                raise RuntimeError("A Groq retornou uma resposta vazia.")

            st.markdown(texto)
            if escolha.finish_reason == "length":
                st.warning("A resposta atingiu o limite de geração e pode estar incompleta.")
            else:
                st.success("Auditoria analítica concluída com sucesso!")
        except Exception as e:
            st.error(f"Erro na infraestrutura de IA: {str(e)}")