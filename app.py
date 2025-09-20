# app.py
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import locale

st.set_page_config(page_title="Calculadora Renda Fixa", layout="wide")

# Definir locale para formato monetário (Brasil)
try:
    locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_ALL, "")

# ---------- Funções auxiliares ----------

# def formatar_moeda(valor):
#     """Formata número como moeda brasileira (R$ 1.234,56)."""
#     return locale.currency(valor, grouping=True, symbol=True)
def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

import requests

def buscar_cdi():
    """
    Busca o CDI diário via API do Banco Central (série SGS 12)
    e converte para taxa anual (% a.a.).
    """
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        dados = resp.json()
        valor_str = dados[0]["valor"]

        # CDI diário em porcentagem
        cdi_diario_pct = float(valor_str.replace(",", "."))
        cdi_diario = cdi_diario_pct / 100.0

        # Converte para taxa anualizada (252 dias úteis)
        cdi_anual = (1 + cdi_diario) ** 252 - 1

        return cdi_anual * 100  # em %
    except Exception:
        return None


def calcular_prazo_em_dias(start_date, end_date):
    return (end_date - start_date).days

def obter_aliquota_ir(prazo_dias):
    if prazo_dias <= 180:
        return 0.225
    elif prazo_dias <= 360:
        return 0.20
    elif prazo_dias <= 720:
        return 0.175
    else:
        return 0.15

def aliquota_iof(dias):
    """Tabela regressiva IOF (0 a 30 dias)."""
    if dias >= 30:
        return 0.0
    return (30 - dias) / 30  # Ex: 1 dia -> 96.67% de IOF, 29 dias -> 3.33%

def calcular_rendimento(valor_investido, taxa_anual_percent, prazo_dias):
    taxa_anual = taxa_anual_percent / 100.0
    taxa_diaria = (1 + taxa_anual) ** (1/365)
    return valor_investido * (taxa_diaria ** prazo_dias)

def calcular_investimento(data_inicio, data_fim, produto, tipo, valor_investido,
                          taxa_anual=None, cdi=None, percentual_cdi=None, taxa_custodia=0.0):
    prazo = calcular_prazo_em_dias(data_inicio, data_fim)
    tributavel = (produto == "CDB")

    # Taxa efetiva anual
    if tipo == "Pré":
        taxa_efetiva = taxa_anual or 0.0
    else:
        taxa_efetiva = (percentual_cdi or 0.0) / 100 * (cdi or 0.0)

    bruto = calcular_rendimento(valor_investido, taxa_efetiva, prazo)
    rendimento = bruto - valor_investido

    # IOF (se aplicável)
    iof = 0.0
    if tributavel and prazo < 30:
        iof = rendimento * aliquota_iof(prazo)

    # IR (se aplicável)
    imposto_ir = 0.0
    if tributavel:
        aliquota = obter_aliquota_ir(prazo)
        imposto_ir = (rendimento - iof) * aliquota

    # Taxa de custódia (sobre o período total)
    custo_custodia = valor_investido * (taxa_custodia/100) * (prazo/365)

    liquido = bruto - imposto_ir - iof - custo_custodia
    rent_liq_pct = (liquido/valor_investido - 1) * 100 if valor_investido > 0 else 0
    rent_anual_pct = ((1 + rent_liq_pct/100) ** (365/prazo) - 1) * 100 if prazo > 0 else 0

    return {
        "produto": produto,
        "tipo": tipo,
        "taxa": taxa_efetiva,
        "prazo": prazo,
        "valor_investido": valor_investido,
        "valor_bruto": bruto,
        "iof": iof,
        "imposto_ir": imposto_ir,
        "custodia": custo_custodia,
        "valor_liquido": liquido,
        "rentabilidade": rent_liq_pct,
        "rentabilidade_anual": rent_anual_pct
    }

def gerar_grafico(valor_investido, taxa_anual, prazo, produto, tipo, cdi=None, percentual_cdi=None, taxa_custodia=0.0):
    """Gera gráfico da evolução do investimento no tempo."""
    dias = list(range(1, prazo+1))
    valores_liq = []
    for d in dias:
        parcial = calcular_investimento(
            date.today(), date.today()+timedelta(days=d), produto, tipo, valor_investido,
            taxa_anual=taxa_anual, cdi=cdi, percentual_cdi=percentual_cdi, taxa_custodia=taxa_custodia
        )
        valores_liq.append(parcial["valor_liquido"])
    fig, ax = plt.subplots(figsize=(7,4))
    ax.plot(dias, valores_liq, label="Valor Líquido")
    ax.set_title("Evolução do Investimento")
    ax.set_xlabel("Dias")
    ax.set_ylabel("Valor (R$)")
    ax.legend()
    return fig

# ---------- Interface Streamlit ----------

st.title("📈 Calculadora de Rendimento — Renda Fixa")

st.write("Calcule e compare CDB / LCI / LCA com IR, IOF e taxa de custódia.")

comparar = st.checkbox("Comparar dois investimentos?")

# CDI automático
cdi_auto = buscar_cdi()
if cdi_auto:
    st.info(f"📊 CDI atual (BCB): {cdi_auto:.2f}% ao ano")
else:
    st.warning("⚠️ Não foi possível buscar CDI automaticamente. Insira manualmente abaixo.")

def render_inputs(prefix):
    st.subheader(prefix)
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data início", value=date.today(), key=prefix+"_start")
        data_fim = st.date_input("Data fim", value=date.today()+timedelta(days=365), key=prefix+"_end")
        produto = st.selectbox("Produto", ("CDB","LCI","LCA"), key=prefix+"_produto")
        tipo = st.selectbox("Tipo de rendimento", ("Pré","Pós"), key=prefix+"_tipo")
    with col2:
        valor_investido = st.number_input("Valor investido (R$)", min_value=100.0, value=1000.0, step=100.0, key=prefix+"_valor")
        taxa_custodia = st.number_input("Taxa de custódia (% ao ano)", min_value=0.0, value=0.0, step=0.01, key=prefix+"_custodia")
        taxa_anual = None
        cdi = None
        percentual_cdi = None
        if tipo == "Pré":
            taxa_anual = st.number_input("Taxa anual (%)", value=10.0, step=0.01, key=prefix+"_taxa")
        else:
            cdi = cdi_auto or st.number_input("CDI anual atual (%)", value=13.65, step=0.01, key=prefix+"_cdi")
            percentual_cdi = st.number_input("Percentual do CDI (%)", value=100.0, step=0.01, key=prefix+"_pcdi")
    return data_inicio, data_fim, produto, tipo, valor_investido, taxa_anual, cdi, percentual_cdi, taxa_custodia

# Execução principal
if comparar:
    col1, col2 = st.columns(2)
    with col1:
        p1 = render_inputs("Investimento 1")
    with col2:
        p2 = render_inputs("Investimento 2")

    inv1 = calcular_investimento(*p1)
    inv2 = calcular_investimento(*p2)

    st.subheader("📊 Comparação")
    df = pd.DataFrame([inv1, inv2])
    df_fmt = df.copy()
    df_fmt["valor_investido"] = df_fmt["valor_investido"].apply(formatar_moeda)
    df_fmt["valor_bruto"] = df_fmt["valor_bruto"].apply(formatar_moeda)
    df_fmt["valor_liquido"] = df_fmt["valor_liquido"].apply(formatar_moeda)
    df_fmt["imposto_ir"] = df_fmt["imposto_ir"].apply(formatar_moeda)
    df_fmt["iof"] = df_fmt["iof"].apply(formatar_moeda)
    df_fmt["custodia"] = df_fmt["custodia"].apply(formatar_moeda)
    st.dataframe(df_fmt)

    melhor = "Investimento 1" if inv1["rentabilidade_anual"] > inv2["rentabilidade_anual"] else "Investimento 2"
    st.success(f"✅ Melhor investimento: {melhor}")

else:
    p = render_inputs("Investimento")
    inv = calcular_investimento(*p)

    st.subheader("📊 Resultado")
    st.write(f"Produto: {inv['produto']} — {inv['tipo']}")
    st.write(f"Prazo: {inv['prazo']} dias")
    st.write(f"Valor investido: {formatar_moeda(inv['valor_investido'])}")
    st.write(f"Valor bruto: {formatar_moeda(inv['valor_bruto'])}")
    st.write(f"IOF: {formatar_moeda(inv['iof'])}")
    st.write(f"Imposto de Renda: {formatar_moeda(inv['imposto_ir'])}")
    st.write(f"Custódia: {formatar_moeda(inv['custodia'])}")
    st.write(f"Valor líquido: {formatar_moeda(inv['valor_liquido'])}")
    st.write(f"Rentabilidade líquida: {inv['rentabilidade']:.2f}%")
    st.write(f"Rentabilidade anual: {inv['rentabilidade_anual']:.2f}%")

    fig = gerar_grafico(inv['valor_investido'], p[5], inv['prazo'], inv['produto'], inv['tipo'], p[6], p[7], p[8])
    st.pyplot(fig)




