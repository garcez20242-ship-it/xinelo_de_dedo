import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Xinelo v6.5", layout="wide", page_icon="🩴")

# --- ESTILIZAÇÃO E TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v6.5 - Sistema Integral")
st.markdown("---")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES CORE ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        return float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except: return 0.0

def gerar_recibo(r):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.ln(10)
        pdf.cell(190, 10, f"Data: {r['Data']}", ln=True)
        pdf.cell(190, 10, f"Cliente: {r['Cliente']}", ln=True)
        pdf.ln(5)
        pdf.multi_cell(190, 8, f"Itens: {r['Resumo']}")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"Total: R$ {limpar_valor(r['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CACHE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_dados():
    abas = ["Estoque", "Pedidos", "Clientes", "Insumos", "Lembretes", "Aquisicoes"]
    leitura = {}
    for a in abas:
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=a, ttl="0s")
            if df is not None and not df.empty:
                leitura[a] = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
            else:
                leitura[a] = pd.DataFrame()
        except:
            leitura[a] = pd.DataFrame()
    return leitura

d = carregar_dados()
df_est = d["Estoque"].sort_values("Modelo") if not d["Estoque"].empty else pd.DataFrame(columns=["Modelo"] + TAMANHOS_PADRAO)
df_ped = d["Pedidos"]
df_cli = d["Clientes"].sort_values("Nome") if not d["Clientes"].empty else pd.DataFrame(columns=["Nome", "Loja", "Cidade", "Telefone"])
df_ins = d["Insumos"]
df_lem = d["Lembretes"]
df_aqui = d["Aquisicoes"]

def salvar_full(aba, df_novo, df_antigo):
    if len(df_antigo) > 0 and len(df_novo) == 0:
        st.error("Erro de proteção: O sistema impediu o reset da planilha.")
        return
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success(f"Dados salvos em {aba}!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Sincronizar Agora"):
        st.cache_data.clear(); st.rerun()
    
    st.divider()
    st.header("📅 Próximos Pagamentos")
    if not df_lem.empty:
        for _, r in df_lem.iterrows():
            st.warning(f"**{r['Nome']}**\nVence: {r['Vencimento']}\nValor: R$ {r['Valor']}")
    
    st.divider()
    st.header("⚠️ Alerta de Estoque")
    for _, r in df_est.iterrows():
        baixo = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
        if baixo: st.error(f"**{r['Modelo']}**:\n{', '.join(baixo)}")

# --- INTERFACE DE ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📦 Aquisições"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário e Entradas")
    col_e1, col_e2 = st.columns([1, 2])
    with col_e1:
        st.write("**Adicionar Unidades**")
        mod_ent = st.selectbox("Modelo para Entrada", df_est['Modelo'].unique())
        tam_ent = st.selectbox("Tamanho para Entrada", TAMANHOS_PADRAO)
        qtd_ent = st.number_input("Quantidade de Entrada", min_value=1)
        if st.button("Confirmar Entrada"):
            df_atu = df_est.copy()
            idx = df_atu.index[df_atu['Modelo'] == mod_ent][0]
            df_atu.at[idx, tam_ent] = int(float(df_atu.at[idx, tam_ent])) + qtd_ent
            salvar_full("Estoque", df_atu, df_est)
    with col_e2:
        st.dataframe(df_est, hide_index=True)

with tabs[1]: # NOVO MODELO
    st.subheader("✨ Cadastrar Novo Produto")
    with st.form("form_novo_mod"):
        n_mod = st.text_input("Nome do Modelo")
        if st.form_submit_button("Salvar Modelo no Banco"):
            if n_mod:
                novo = {"Modelo": n_mod}; novo.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar_full("Estoque", pd.concat([df_est, pd.DataFrame([novo])], ignore_index=True), df_est)

with tabs[2]: # VENDAS
    st.subheader("🛒 Carrinho de Vendas")
    c1, c2 = st.columns(2)
    with c1:
        v_cliente = st.selectbox("Selecionar Cliente", list(df_cli['Nome'].unique()) + ["Avulso"])
        v_modelo = st.selectbox("Selecionar Modelo", df_est['Modelo'].unique())
        v_tamanho = st.selectbox("Selecionar Tamanho", TAMANHOS_PADRAO)
        v_preco = st.number_input("Preço de Venda R$", min_value=0.0)
        v_quantidade = st.number_input("Qtd Vendida", min_value=1)
        if st.button("➕ Adicionar ao Carrinho"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_modelo, "Tam": v_tamanho, "Qtd": v_quantidade, "Pre": v_preco})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            total_venda, lista_resumo = 0, []
            for i, item in enumerate(st.session_state.cart):
                st.write(f"**{item['Mod']} {item['Tam']}** | x{item['Qtd']} | R$ {item['Pre']*item['Qtd']:.2f}")
                total_venda += item['Pre']*item['Qtd']
                lista_resumo.append(f"{item['Mod']}({item['Tam']}x{item['Qtd']})")
            
            v_status = st.radio("Pagamento:", ["Pago", "Pendente"], horizontal=True)
            if st.button("🏁 Finalizar Venda e Baixar Estoque"):
                df_e_atu = df_est.copy()
                for item in st.session_state.cart:
                    idx = df_e_atu.index[df_e_atu['Modelo'] == item['Mod']][0]
                    df_e_atu.at[idx, item['Tam']] = int(float(df_e_atu.at[idx, item['Tam']])) - item['Qtd']
                
                salvar_full("Estoque", df_e_atu, df_est)
                nova_venda = {"Data": get_data_hora(), "Cliente": v_cliente, "Resumo": " | ".join(lista_resumo), "Valor Total": total_venda, "Status Pagto": v_status}
                salvar_full("Pedidos", pd.concat([df_ped, pd.DataFrame([nova_venda])], ignore_index=True), df_ped)
                st.session_state.cart = []; st.rerun()

with tabs[3]: # INSUMOS
    st.subheader("🛠️ Gastos com Insumos")
    with st.form("form_insumo"):
        i_desc = st.text_input("Descrição do Gasto"); i_val = st.number_input("Valor R$")
        if st.form_submit_button("Registrar Insumo"):
            salvar_full("Insumos", pd.concat([df_ins, pd.DataFrame([{"Data": get_data_hora(), "Descricao": i_desc, "Valor": i_val}])], ignore_index=True), df_ins)
    st.dataframe(df_ins, hide_index=True)

with tabs[4]: # CLIENTES
    st.subheader("👥 Cadastro Completo de Clientes")
    with st.form("form_cliente_full"):
        col_c1, col_c2 = st.columns(2)
        c_nome = col_c1.text_input("Nome Completo")
        c_loja = col_c2.text_input("Nome da Loja")
        c_cida = col_c1.text_input("Cidade")
        c_tele = col_c2.text_input("WhatsApp/Telefone")
        if st.form_submit_button("Cadastrar Cliente"):
            salvar_full("Clientes", pd.concat([df_cli, pd.DataFrame([{"Nome": c_nome, "Loja": c_loja, "Cidade": c_cida, "Telefone": c_tele}])], ignore_index=True), df_cli)
    st.dataframe(df_cli, hide_index=True)

with tabs[5]: # EXTRATO
    st.subheader("🧾 Extrato de Vendas")
    if not df_ped.empty:
        for idx, r in df_ped.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                col_ex1, col_ex2, col_ex3, col_ex4 = st.columns([0.1, 0.1, 0.1, 0.7])
                if col_ex1.button("🗑️", key=f"del_ped_{idx}"):
                    salvar_full("Pedidos", df_ped.drop(idx), df_ped)
                if "Pendente" in str(r['Status Pagto']) and col_ex2.button("✅", key=f"pay_ped_{idx}"):
                    df_p_atu = df_ped.copy(); df_p_atu.at[idx, 'Status Pagto'] = "Pago"
                    salvar_full("Pedidos", df_p_atu, df_ped)
                col_ex3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_ped_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

with tabs[6]: # LEMBRETES
    st.subheader("📅 Gestão de Lembretes de Pagamento")
    with st.form("form_lembrete"):
        l_nome = st.text_input("Descrição do Pagamento")
        l_venc = st.date_input("Data de Vencimento")
        l_valor = st.number_input("Valor R$")
        if st.form_submit_button("Agendar"):
            salvar_full("Lembretes", pd.concat([df_lem, pd.DataFrame([{"Data": get_data_hora(), "Nome": l_nome, "Vencimento": str(l_venc), "Valor": l_valor}])], ignore_index=True), df_lem)
    
    st.divider()
    if not df_lem.empty:
        for idx, r in df_lem.iterrows():
            col_l1, col_l2, col_l3 = st.columns([0.1, 0.1, 0.8])
            if col_l1.button("✅", key=f"concluir_{idx}"):
                salvar_full("Lembretes", df_lem.drop(idx), df_lem)
            if col_l2.button("🗑️", key=f"apagar_{idx}"):
                salvar_full("Lembretes", df_lem.drop(idx), df_lem)
            st.write(f"📌 **{r['Nome']}** | Vencimento: {r['Vencimento']} | Valor: R$ {r['Valor']}")

with tabs[7]: # AQUISIÇÕES
    st.subheader("📦 Registro de Aquisições (Matéria-Prima/Estoque)")
    with st.form("form_aqui"):
        a_res = st.text_input("Resumo da Aquisição"); a_val = st.number_input("Valor Total Investido R$")
        if st.form_submit_button("Registrar Compra"):
            salvar_full("Aquisicoes", pd.concat([df_aqui, pd.DataFrame([{"Data": get_data_hora(), "Resumo": a_res, "Valor Total": a_val}])], ignore_index=True), df_aqui)
    st.dataframe(df_aqui, hide_index=True)
