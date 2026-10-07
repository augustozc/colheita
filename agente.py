import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
SALDO_INICIAL = 429_000.00
RETIRADA_MENSAL = 11_000.00
PRAZO_MESES = 36


def numero(valor: str) -> float:
    """Converte valor numérico do SGS para float."""
    return float(valor.strip().replace(",", "."))


def consultar_sgs(codigo_serie: int, inicio: date) -> list[dict]:
    parametros = {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": date.today().strftime("%d/%m/%Y"),
    }
    response = requests.get(
        SGS_URL.format(serie=codigo_serie),
        params=parametros,
        timeout=30,
    )
    response.raise_for_status()

    dados = response.json()
    if not isinstance(dados, list) or not dados:
        raise RuntimeError(f"SGS não retornou dados para a série {codigo_serie}.")

    registros = []
    for item in dados:
        registros.append({
            "data": datetime.strptime(item["data"], "%d/%m/%Y").date(),
            "valor": numero(item["valor"]),
        })
    return sorted(registros, key=lambda item: item["data"])


def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def percentual(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + "%"


def gerar_projecao(
    selic_anual_pct: float,
    inflacao_anual_pct: float,
) -> tuple[list[dict], float, float]:
    # Conversão de taxa anual para mensal efetiva; premissa simplificadora.
    taxa_mensal = (1 + selic_anual_pct / 100) ** (1 / 12) - 1
    saldo = SALDO_INICIAL
    tabela = []
    total_retirado = 0.0

    for mes in range(1, PRAZO_MESES + 1):
        saldo_inicial_mes = saldo
        rendimento = saldo * taxa_mensal
        saldo += rendimento

        retirada = min(RETIRADA_MENSAL, saldo)
        saldo -= retirada
        total_retirado += retirada

        tabela.append({
            "mes": mes,
            "saldo_inicial": saldo_inicial_mes,
            "rendimento": rendimento,
            "retirada": retirada,
            "saldo_final": saldo,
        })

    saldo_real = saldo / ((1 + inflacao_anual_pct / 100) ** (PRAZO_MESES / 12))
    return tabela, total_retirado, saldo_real


def gerar_relatorio() -> Path:
    # Busca uma janela ampla para garantir pelo menos 12 observações mensais.
    inicio = date.today() - timedelta(days=900)

    # SGS 432: meta Selic definida pelo Copom, em % ao ano.
    registros_selic = consultar_sgs(432, inicio)
    ultimo_selic = registros_selic[-1]

    # SGS 433: variação mensal do IPCA, em %.
    registros_ipca = consultar_sgs(433, inicio)
    ultimos_ipca = registros_ipca[-12:]
    if len(ultimos_ipca) < 12:
        raise RuntimeError(
            "O SGS retornou menos de 12 observações mensais do IPCA."
        )

    # Inflação acumulada composta dos últimos 12 registros mensais observados.
    fator_ipca = 1.0
    for registro in ultimos_ipca:
        fator_ipca *= 1 + registro["valor"] / 100
    inflacao_12m_pct = (fator_ipca - 1) * 100

    tabela, total_retirado, saldo_real = gerar_projecao(
        ultimo_selic["valor"],
        inflacao_12m_pct,
    )
    saldo_final = tabela[-1]["saldo_final"]

    linhas_tabela = [
        "| Mês | Saldo inicial | Rendimento estimado | Retirada | Saldo final |",
        "|---:|---:|---:|---:|---:|",
    ]
    for linha in tabela:
        linhas_tabela.append(
            f"| {linha['mes']} "
            f"| {moeda(linha['saldo_inicial'])} "
            f"| {moeda(linha['rendimento'])} "
            f"| {moeda(linha['retirada'])} "
            f"| {moeda(linha['saldo_final'])} |"
        )

    conteudo = f"""# Relatório ilustrativo de estresse patrimonial

**Data de geração:** {date.today().strftime("%d/%m/%Y")}

> Este é um cenário hipotético, não uma recomendação financeira. Dados passados
> não garantem retornos futuros. A simulação não representa exatamente o
> rendimento líquido de um título do Tesouro Direto.

## Dados consultados

- **Meta Selic:** {percentual(ultimo_selic["valor"])} a.a., SGS série 432,
  observação de {ultimo_selic["data"].strftime("%d/%m/%Y")}.
- **IPCA acumulado nos últimos 12 registros mensais:** {percentual(inflacao_12m_pct)},
  calculado a partir da SGS série 433, da observação
  {ultimos_ipca[0]["data"].strftime("%d/%m/%Y")} até
  {ultimos_ipca[-1]["data"].strftime("%d/%m/%Y")}.
- O IPCA acima é **inflação observada**, não uma projeção futura do Boletim Focus.
  Não foi consultada nem inferida expectativa Focus.

## Premissas da simulação

- Saldo inicial: **{moeda(SALDO_INICIAL)}**.
- Retirada ao fim de cada mês: **{moeda(RETIRADA_MENSAL)}**, por até
  {PRAZO_MESES} meses.
- A meta Selic observada é mantida constante durante todo o cenário; isso é
  apenas uma hipótese, não uma previsão.
- A taxa anual foi convertida em taxa mensal efetiva pela fórmula
  `(1 + taxa anual)^(1/12) - 1`.
- A inflação observada nos últimos 12 registros é mantida constante por 36 meses
  somente para estimar o valor real do saldo.
- Não foram descontados Imposto de Renda, taxas, custos, diferenças entre a
  meta Selic e o retorno efetivo do título, nem regras de liquidação.
- O cálculo aplica o rendimento mensal antes da retirada.

## Resultado ilustrativo

- Total de retiradas no cenário: **{moeda(total_retirado)}**.
- Saldo nominal estimado ao fim de 36 meses: **{moeda(saldo_final)}**.
- Saldo final em poder de compra de hoje, usando a hipótese de inflação acima:
  **{moeda(saldo_real)}**.

O saldo real é uma conversão aproximada: saldo nominal futuro dividido pelo
fator de inflação acumulada hipotético de três anos. Não representa uma
rentabilidade real garantida.

## Fluxo mensal

{chr(10).join(linhas_tabela)}

## Limitações

A meta Selic não é necessariamente igual ao retorno líquido de um investimento.
O resultado real depende da trajetória futura dos juros e da inflação, dos
impostos, das taxas e das condições específicas do título. Esta simulação
mantém as taxas constantes para tornar as premissas visíveis; não prevê o
mercado nem substitui orientação profissional.
"""

    # O web.py usa o diretório de trabalho temporário para localizar o relatório.
    caminho = Path.cwd() / "Relatorio_Estresse_Patrimonial.md"
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


if __name__ == "__main__":
    try:
        arquivo = gerar_relatorio()
        print(f"Relatório gerado: {arquivo}", flush=True)
    except Exception as erro:
        print(f"Erro ao gerar relatório: {erro}", file=sys.stderr, flush=True)
        sys.exit(1)