# app.py
from datetime import date
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Calculadora Renda Fixa", layout="wide")

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

def calcular_rendimento(valor_investido, taxa_anual_percent, prazo_dias):
    if prazo_dias <= 0:
        return valor_investido
    taxa_anual = taxa_anual_percent / 100.0
    taxa_diaria = (1 + taxa_anual) ** (1/365)
    return valor_investido * (taxa_diaria ** prazo_dias)

def calcular_imposto(valor_bruto, valor_investido, prazo_dias, tributavel):
    if not tributavel:
        return 0.0
    rendimento = valor_bruto - valor_investido
    aliquota = obter_aliquota_ir(prazo_dias)
    return rendimento * aliquota

def calcular_investimento_dict(data_inicio, data_fim, produto, tipo, valor_investido, taxa_anual_percent=None, cdi=None, percentual_cdi=None):
    prazo = calcular_prazo_em_dias(data_inicio, data_fim)
    tributavel = (produto == "CDB")

    if tipo == "Pré":
        taxa = taxa_anual_percent if taxa_anual_percent is not None else 0.0
        taxa_anual = taxa
    else:
        taxa = percentual_cdi if percentual_cdi is not None else 0.0
        taxa_anual = (percentual_cdi / 100.0) * (cdi if cdi is not None else 0.0)

    bruto = calcular_rendimento(valor_investido, taxa_anual, prazo)
    imposto = calcular_imposto(bruto, valor_investido, prazo, tributavel)
    liquido = bruto - imposto
    rent_liq_pct = (liquido / valor_investido - 1) * 100 if valor_investido>0 else 0
    rent_anual_pct = ((1 + rent_liq_pct/100) ** (365 / prazo) -1) * 100 if prazo>0 else 0

    return {
        "produto": produto,
        "tipo": tipo,
        "taxa": taxa,
        "prazo": prazo,
        "valor_investido": valor_investido,
        "valor_bruto": bruto,
        "imposto": imposto,
        "valor_liquido": liquido,
        "rentabilidade": rent_liq_pct,
        "rentabilidade_anual": rent_anual_pct
    }

def render_inputs(prefix):
    st.header(prefix)
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data início", value=date.today(), key=prefix+"_start")
        data_fim = st.date_input("Data fim", value=date.today(), key=prefix+"_end")
        produto = st.selectbox("Produto", ("CDB","LCI","LCA"), key=prefix+"_produto")
        tipo = st.selectbox("Tipo de rendimento", ("Pré","Pós"), key=prefix+"_tipo")
    with col2:
        valor_investido = st.number_input("Valor investido (R$)", min_value=0.0, value=1000.0, step=100.0, key=prefix+"_valor")
        taxa_anual = None
        cdi = None
        percentual_cdi = None
        if tipo == "Pré":
            taxa_anual = st.number_input("Taxa anual (%)", value=10.0, step=0.01, key=prefix+"_taxa")
        else:
            cdi = st.number_input("CDI anual atual (%)", value=13.75, step=0.01, key=prefix+"_cdi")
            percentual_cdi = st.number_input("Percentual do CDI (%)", value=100.0, step=0.01, key=prefix+"_pcdi")
    return {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "produto": produto,
        "tipo": tipo,
        "valor_investido": valor_investido,
        "taxa_anual": taxa_anual,
        "cdi": cdi,
        "percentual_cdi": percentual_cdi
    }

st.title("Calculadora de Rendimento — Renda Fixa")
st.write("Calcule e compare CDB / LCI / LCA. Obs: IOF não está sendo considerado aqui.")

comparar = st.checkbox("Comparar dois investimentos?")

if comparar:
    col_left, col_right = st.columns(2)
    with col_left:
        in1 = render_inputs("Inv 1")
    with col_right:
        in2 = render_inputs("Inv 2")

    inv1 = calcular_investimento_dict(
        in1["data_inicio"], in1["data_fim"], in1["produto"], in1["tipo"], in1["valor_investido"],
        taxa_anual_percent=in1["taxa_anual"], cdi=in1["cdi"], percentual_cdi=in1["percentual_cdi"]
    )
    inv2 = calcular_investimento_dict(
        in2["data_inicio"], in2["data_fim"], in2["produto"], in2["tipo"], in2["valor_investido"],
        taxa_anual_percent=in2["taxa_anual"], cdi=in2["cdi"], percentual_cdi=in2["percentual_cdi"]
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Investimento 1")
        st.metric("Valor Líquido (R$)", f"{inv1['valor_liquido']:.2f}")
        st.metric("Rent. Anual (%)", f"{inv1['rentabilidade_anual']:.2f}")
        st.write(f"Produto: {inv1['produto']} — {inv1['tipo']}")
        st.write(f"Prazo (dias): {inv1['prazo']}")
    with col2:
        st.subheader("Investimento 2")
        st.metric("Valor Líquido (R$)", f"{inv2['valor_liquido']:.2f}")
        st.metric("Rent. Anual (%)", f"{inv2['rentabilidade_anual']:.2f}")
        st.write(f"Produto: {inv2['produto']} — {inv2['tipo']}")
        st.write(f"Prazo (dias): {inv2['prazo']}")

    melhor = "Investimento 1" if inv1["rentabilidade_anual"] > inv2["rentabilidade_anual"] else "Investimento 2"
    st.success(f"✅ Melhor investimento segundo rentabilidade anual: {melhor}")

    df = pd.DataFrame([inv1, inv2])
    df_display = df[["produto","tipo","taxa","prazo","valor_investido","valor_bruto","imposto","valor_liquido","rentabilidade","rentabilidade_anual"]]
    st.dataframe(df_display)

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar comparação (CSV)", data=csv, file_name="comparacao_renda_fixa.csv", mime="text/csv")
else:
    in1 = render_inputs("Investimento")
    inv = calcular_investimento_dict(
        in1["data_inicio"], in1["data_fim"], in1["produto"], in1["tipo"], in1["valor_investido"],
        taxa_anual_percent=in1["taxa_anual"], cdi=in1["cdi"], percentual_cdi=in1["percentual_cdi"]
    )
    st.subheader("Resultado")
    st.write(f"Produto: {inv['produto']}")
    st.write(f"Tipo: {inv['tipo']}")
    st.write(f"Prazo (dias): {inv['prazo']}")
    st.write(f"Valor investido: R$ {inv['valor_investido']:.2f}")
    st.write(f"Valor bruto: R$ {inv['valor_bruto']:.2f}")
    st.write(f"Imposto IR: R$ {inv['imposto']:.2f}")
    st.write(f"Valor líquido: R$ {inv['valor_liquido']:.2f}")
    st.write(f"Rentabilidade líquida: {inv['rentabilidade']:.2f}%")
    st.write(f"Rentabilidade anual: {inv['rentabilidade_anual']:.2f}%")

    df = pd.DataFrame([inv])
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar resultado (CSV)", data=csv, file_name="resultado_renda_fixa.csv", mime="text/csv")
