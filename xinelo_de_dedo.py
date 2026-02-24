import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Xinelo v6.7", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Xinelo de Dedo v6.7 - Versão Estável")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES AUXILIARES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        return float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except: return 0.0

def gerar_recibo(r):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
        pdf.set_font("Arial", "", 12); pdf.ln(10)
        pdf.cell(190, 10, f"Data: {r.get('Data', '')}", ln=True)
        pdf.cell(190, 10, f"Cliente: {r.get('Cliente', '')}", ln=True)
        pdf.multi_cell(190, 8, f"Itens: {r.get('Resumo', '')}")
        pdf.cell(190, 10, f"Total: R$ {limpar_valor(r.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E LIMPEZA DE COLUNAS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_dados():
    abas_necessarias = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor"],
        "Aquisicoes": ["Data", "Resumo", "Valor Total"]
    }
    leitura = {}
    for aba, colunas_esperadas in abas_necessarias.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip() # Remove espaços extras nos nomes das colunas
                # Garante que colunas essenciais existam
                for col in colunas_esperadas:
                    if col not in df.columns:
                        df[col] = ""
                leitura[aba] = df
            else:
                leitura[aba] = pd.DataFrame(columns=colunas_esperadas)
        except:
            leitura[aba] = pd.DataFrame(columns=colunas_esperadas)
    return leitura

d = carregar_dados()
df_est = d["Estoque"]
df_ped = d["Pedidos"]
df_cli = d["Clientes"]
df_ins = d["Insumos"]
df_lem = d["Lembretes"]
df_aqui = d["Aquisicoes"]

def salvar_full(aba, df_novo, df_antigo):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear(); st.success("Atualizado!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("🔄 Forçar Sincronização"): st.cache_data.clear(); st.rerun()
    
    st.divider(); st.header("📅 Lembretes")
    if not df_lem.empty:
        for _, r in df_lem.iterrows():
            if r['Nome']: st.warning(f"**{r['Nome']}**\nVence: {r['Vencimento']}\nValor: R$ {r['Valor']}")
    
    st.divider(); st.header("⚠️ Estoque Baixo")
    if not df_est.empty:
        for _, r in df_est.iterrows():
            baixo = [f"{t}({int(float(r[t])) if r[t]!='' else 0})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
            if baixo: st.error(f"**{r['Modelo']}**:\n{', '.join(baixo)}")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📦 Aquisições"])

with tabs[0]: # ESTOQUE
    c1, c2 = st.columns([1, 2])
    with c1:
        if not df_est.empty:
            mod_ent = st.selectbox("Modelo", df_est['Modelo'].unique())
            tam_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            qtd_ent = st.number_input("Qtd", min_value=1)
            if st.button("Confirmar Entrada"):
                df_atu = df_est.copy()
                idx = df_atu.index[df_atu['Modelo'] == mod_ent][0]
                val_atual = int(float(df_atu.at[idx, tam_ent])) if df_atu.at[idx, tam_ent] != "" else 0
                df_atu.at[idx, tam_ent] = val_atual + qtd_ent
                salvar_full("Estoque", df_atu, df_est)
    with c2: st.dataframe(df_est, hide_index=True)

with tabs[1]: # NOVO MODELO
    with st.form("f_nm"):
        n_mod = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if n_mod:
                novo = {"Modelo": n_mod}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar_full("Estoque", pd.concat([df_est, pd.DataFrame([novo])], ignore_index=True), df_est)

with tabs[2]: # VENDAS
    c1, c2 = st.columns(2)
    with c1:
        lista_clientes = list(df_cli['Nome'].unique()) if 'Nome' in df_cli.columns else []
        v_cliente = st.selectbox("Cliente", lista_clientes + ["Avulso"])
        v_modelo = st.selectbox("Modelo ", df_est['Modelo'].unique()) if not df_est.empty else None
        v_tamanho = st.selectbox("Tamanho ", TAMANHOS_PADRAO)
        v_preco = st.number_input("Preço R$ ", min_value=0.0)
        v_quantidade = st.number_input("Qtd Vendida ", min_value=1)
        if st.button("➕ Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_modelo, "Tam": v_tamanho, "Qtd": v_quantidade, "Pre": v_preco})
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} | R$ {it['Pre']*it['Qtd']:.2f}")
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_st = st.radio("Pagamento", ["Pago", "Pendente"], horizontal=True)
            if st.button("🏁 Finalizar Venda"):
                df_e = df_est.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    val_atu = int(float(df_e.at[idx, it['Tam']])) if df_e.at[idx, it['Tam']] != "" else 0
                    df_e.at[idx, it['Tam']] = val_atu - it['Qtd']
                salvar_full("Estoque", df_e, df_est)
                salvar_full("Pedidos", pd.concat([df_ped, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cliente, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_st}])], ignore_index=True), df_ped)
                st.session_state.cart = []; st.rerun()

with tabs[4]: # CLIENTES (RESTAURADO COMPLETO)
    with st.form("f_cl"):
        c_n = st.text_input("Nome"); c_l = st.text_input("Loja"); c_c = st.text_input("Cidade"); c_t = st.text_input("Tel")
        if st.form_submit_button("Salvar Cliente"):
            salvar_full("Clientes", pd.concat([df_cli, pd.DataFrame([{"Nome": c_n, "Loja": c_l, "Cidade": c_c, "Telefone": c_t}])], ignore_index=True), df_cli)
    st.dataframe(df_cli, hide_index=True)

with tabs[5]: # EXTRATO (COM PDF E LIXEIRA)
    if not df_ped.empty:
        for idx, r in df_ped.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if c1.button("🗑️", key=f"d_{idx}"): salvar_full("Pedidos", df_ped.drop(idx), df_ped)
                if "Pendente" in str(r['Status Pagto']) and c2.button("✅", key=f"p_{idx}"):
                    df_up = df_ped.copy(); df_up.at[idx, 'Status Pagto'] = "Pago"; salvar_full("Pedidos", df_up, df_ped)
                c3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"f_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

with tabs[6]: # LEMBRETES (BOTÕES ✅ e 🗑️)
    with st.form("f_lem"):
        l_n = st.text_input("Descrição"); l_v = st.date_input("Vencimento"); l_val = st.number_input("Valor R$")
        if st.form_submit_button("Agendar Pagamento"):
            salvar_full("Lembretes", pd.concat([df_lem, pd.DataFrame([{"Data": get_data_hora(), "Nome": l_n, "Vencimento": str(l_v), "Valor": l_val}])], ignore_index=True), df_lem)
    if not df_lem.empty:
        for idx, r in df_lem.iterrows():
            col1, col2, col3 = st.columns([0.1, 0.1, 0.8])
            if col1.button("✅", key=f"ok_{idx}"): salvar_full("Lembretes", df_lem.drop(idx), df_lem)
            if col2.button("🗑️", key=f"del_{idx}"): salvar_full("Lembretes", df_lem.drop(idx), df_lem)
            st.write(f"📌 **{r['Nome']}** - Vencimento: {r['Vencimento']} - R$ {r['Valor']}")

with tabs[7]: # AQUISIÇÕES
    with st.form("f_aq"):
        a_r = st.text_input("Resumo da Compra"); a_v = st.number_input("Valor Total R$")
        if st.form_submit_button("Registrar Aquisição"):
            salvar_full("Aquisicoes", pd.concat([df_aqui, pd.DataFrame([{"Data": get_data_hora(), "Resumo": a_r, "Valor Total": a_v}])], ignore_index=True), df_aqui)
    st.dataframe(df_aqui, hide_index=True)
