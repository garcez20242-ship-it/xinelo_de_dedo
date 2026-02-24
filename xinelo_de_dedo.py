import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Xinelo v6.3", layout="wide", page_icon="🩴")

# --- TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v6.3")
st.markdown("---")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES DE APOIO ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(r):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data: {r['Data']}", ln=True)
        pdf.cell(190, 8, f"Cliente: {r['Cliente']}", ln=True)
        pdf.ln(5)
        pdf.multi_cell(190, 8, f"Resumo dos Itens:\n{r['Resumo']}")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"TOTAL: R$ {limpar_valor(r['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO COM CACHE OTIMIZADO (EVITA ERRO 429) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # Aumentado para 60 segundos para poupar a cota do Google
def carregar_dados_seguro():
    abas = ["Estoque", "Pedidos", "Clientes", "Insumos", "Lembretes", "Aquisicoes"]
    dados_carregados = {}
    
    for aba in abas:
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                dados_carregados[aba] = df
            else:
                dados_carregados[aba] = pd.DataFrame()
        except Exception as e:
            # Se der erro 429, ele retorna um DF vazio e avisa na tela
            st.error(f"⚠️ O Google está sobrecarregado (Erro 429). Aguarde 30 segundos. Aba: {aba}")
            dados_carregados[aba] = pd.DataFrame()
            
    return dados_carregados

# Carregamento centralizado
d = carregar_dados_seguro()

# Distribuição das variáveis
df_estoque = d.get("Estoque", pd.DataFrame()).sort_values("Modelo") if not d.get("Estoque", pd.DataFrame()).empty else pd.DataFrame(columns=["Modelo"] + TAMANHOS_PADRAO)
df_pedidos = d.get("Pedidos", pd.DataFrame())
df_clientes = d.get("Clientes", pd.DataFrame()).sort_values("Nome") if not d.get("Clientes", pd.DataFrame()).empty else pd.DataFrame(columns=["Nome", "Loja", "Cidade", "Telefone"])
df_insumos = d.get("Insumos", pd.DataFrame())
df_lembretes = d.get("Lembretes", pd.DataFrame())
df_aquisicoes = d.get("Aquisicoes", pd.DataFrame())

def salvar_blindado(aba, df_novo, df_antigo):
    if len(df_antigo) > 0 and len(df_novo) == 0:
        st.error("🚨 BLOQUEIO: Tentativa de apagar dados detectada. Tente novamente.")
        return False
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Sincronizado!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        if "429" in str(e):
            st.error("🚨 O Google atingiu o limite de envios por minuto. Aguarde 15 segundos antes de tentar salvar de novo.")
        else:
            st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Limpar Cache e Atualizar"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("📅 Contas a Pagar (Lembretes)")
    if not df_lembretes.empty:
        total_contas = df_lembretes['Valor'].apply(limpar_valor).sum()
        st.warning(f"**Total Pendente: R$ {total_contas:.2f}**")
        for _, r in df_lembretes.iterrows():
            st.caption(f"📌 {r.get('Nome', 'S/N')} - R$ {limpar_valor(r.get('Valor', 0)):.2f}")

    st.divider()
    st.header("⚠️ Estoque Baixo")
    if not df_estoque.empty:
        for _, r in df_estoque.iterrows():
            crit = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
            if crit: st.error(f"**{r['Modelo']}**\n{', '.join(crit)}")

# --- ABAS (SEM ALTERAÇÃO NA LÓGICA, APENAS NA ESTABILIDADE) ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

with tabs[0]: # Estoque
    st.subheader("📋 Inventário Completo")
    st.dataframe(df_estoque, hide_index=True)

with tabs[1]: # Novo Modelo
    with st.form("form_nm", clear_on_submit=True):
        nome_n = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if nome_n:
                novo = {"Modelo": nome_n}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar_blindado("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])], ignore_index=True), df_estoque)

with tabs[2]: # Vendas
    c1, c2 = st.columns(2)
    with c1:
        v_cl = st.selectbox("Cliente", list(df_clientes['Nome'].unique()) + ["Avulso"])
        v_mo = st.selectbox("Modelo", df_estoque['Modelo'].unique()) if not df_estoque.empty else None
        v_ta = st.selectbox("Tamanho ", TAMANHOS_PADRAO)
        v_pr = st.number_input("Preço Unitário R$", min_value=0.0)
        v_qt = st.number_input("Qtd Itens", min_value=1)
        if st.button("➕ Adicionar Itens"):
            if 'c' not in st.session_state: st.session_state.c = []
            st.session_state.c.append({"Mod": v_mo, "Tam": v_ta, "Qtd": v_qt, "Pre": v_pr})
            st.rerun()
    with c2:
        if 'c' in st.session_state and st.session_state.c:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.c):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} - R$ {it['Pre']*it['Qtd']:.2f}")
                if st.button("Remover", key=f"r_{i}"): st.session_state.c.pop(i); st.rerun()
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_st = st.radio("Pagamento", ["Pago", "Pendente"], horizontal=True)
            if st.button("🚀 Finalizar Venda", type="primary"):
                df_e = df_estoque.copy()
                for it in st.session_state.c:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar_blindado("Estoque", df_e, df_estoque)
                salvar_blindado("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cl, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_st}])], ignore_index=True), df_pedidos)
                st.session_state.c = []; st.rerun()

with tabs[3]: # Insumos
    with st.form("form_ins"):
        desc_i = st.text_input("Gasto com Insumo"); val_i = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar Gasto"):
            salvar_blindado("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])], ignore_index=True), df_insumos)
    st.dataframe(df_insumos, hide_index=True)

with tabs[4]: # Clientes
    with st.form("form_cli"):
        n = st.text_input("Nome"); l = st.text_input("Loja"); ci = st.text_input("Cidade"); t = st.text_input("Tel")
        if st.form_submit_button("Salvar Cliente"):
            salvar_blindado("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": ci, "Telefone": t}])], ignore_index=True), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

with tabs[5]: # Extrato
    if not df_pedidos.empty:
        for idx, r in df_pedidos.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if col1.button("🗑️", key=f"del_{idx}"): salvar_blindado("Pedidos", df_pedidos.drop(idx), df_pedidos)
                if "Pendente" in str(r['Status Pagto']) and col2.button("✅", key=f"ok_{idx}"):
                    df_up = df_pedidos.copy(); df_up.at[idx, 'Status Pagto'] = "Pago"; salvar_blindado("Pedidos", df_up, df_pedidos)
                col3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

with tabs[6]: # Lembretes
    with st.form("form_lem"):
        t_l = st.text_input("O que pagar?"); v_l = st.number_input("Valor R$ ", min_value=0.0)
        if st.form_submit_button("Agendar Pagamento"):
            salvar_blindado("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Data": get_data_hora(), "Nome": t_l, "Valor": v_l}])], ignore_index=True), df_lembretes)
    st.dataframe(df_lembretes, hide_index=True)
