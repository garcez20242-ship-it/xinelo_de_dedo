import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v7.2", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Master v7.2")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES ---
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
        pdf.cell(190, 10, "DOCUMENTO DE REGISTRO", ln=True, align="C")
        pdf.set_font("Arial", "", 12); pdf.ln(10)
        pdf.cell(190, 10, f"Data: {r.get('Data', '')}", ln=True)
        pdf.multi_cell(190, 8, f"Resumo: {r.get('Resumo', '')}")
        pdf.cell(190, 10, f"Total: R$ {limpar_valor(r.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados():
    abas_necessarias = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor"]
    }
    leitura = {}
    for aba, colunas in abas_necessarias.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                for c in colunas:
                    if c not in df.columns: df[c] = ""
                # ORGANIZAÇÃO ALFABÉTICA NO ESTOQUE
                if aba == "Estoque":
                    df = df.sort_values(by="Modelo", ascending=True)
                leitura[aba] = df
            else: leitura[aba] = pd.DataFrame(columns=colunas)
        except: leitura[aba] = pd.DataFrame(columns=colunas)
    return leitura

d = carregar_dados()
df_est, df_ped, df_cli, df_ins, df_lem = d["Estoque"], d["Pedidos"], d["Clientes"], d["Insumos"], d["Lembretes"]

def salvar(aba, df_n):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_n.astype(str).replace('nan', ''))
        st.cache_data.clear()
        return True
    except Exception as e: 
        st.error(f"Erro ao salvar em {aba}: {e}")
        return False

# --- BARRA LATERAL ---
with st.sidebar:
    if st.button("🔄 Atualizar Dados"): st.cache_data.clear(); st.rerun()
    st.header("📅 Lembretes Ativos")
    for _, r in df_lem.iterrows():
        if r['Nome']: st.warning(f"**{r['Nome']}** - R$ {r['Valor']}")

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novos Modelos", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Gestão de Inventário (Ordem Alfabética)")
    st.dataframe(df_est, hide_index=True)
    
    with st.expander("➕ Entrada de Compra (Lote Multi-Modelo)", expanded=True):
        if 'entrada_lote' not in st.session_state: st.session_state.entrada_lote = []
        c1, c2, c3 = st.columns(3)
        # Modelos em ordem alfabética no selectbox
        modelos_ordenados = sorted(df_est['Modelo'].unique()) if not df_est.empty else []
        mod_e = c1.selectbox("Modelo", modelos_ordenados)
        tam_e = c2.selectbox("Tamanho", TAMANHOS_PADRAO)
        qtd_e = c3.number_input("Qtd", min_value=1, key="input_qtd_entrada")
        
        if st.button("Adicionar ao Lote"):
            st.session_state.entrada_lote.append({"Modelo": mod_e, "Tam": tam_e, "Qtd": qtd_e})
            st.rerun()
        
        if st.session_state.entrada_lote:
            st.write("**Lote de Entrada:**")
            st.table(pd.DataFrame(st.session_state.entrada_lote))
            
            if st.button("❌ Limpar Lote"):
                st.session_state.entrada_lote = []
                st.rerun()
                
            val_total_compra = st.number_input("Valor Total da Compra (R$)", min_value=0.0)
            
            if st.button("🏁 Finalizar e Salvar no Banco", type="primary"):
                with st.spinner("Sincronizando..."):
                    df_atu = df_est.copy()
                    res_compra = []
                    for item in st.session_state.entrada_lote:
                        idx = df_atu.index[df_atu['Modelo'] == item['Modelo']][0]
                        v_atu = int(float(df_atu.at[idx, item['Tam']])) if df_atu.at[idx, item['Tam']] != "" else 0
                        df_atu.at[idx, item['Tam']] = v_atu + item['Qtd']
                        res_compra.append(f"{item['Modelo']}({item['Tam']}x{item['Qtd']})")
                    
                    if salvar("Estoque", df_atu):
                        time.sleep(1)
                        nova_v = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "FORNECEDOR", "Resumo": f"ENTRADA: {' | '.join(res_compra)}", "Valor Total": val_total_compra, "Status Pagto": "Pago"}])
                        if salvar("Pedidos", pd.concat([df_ped, nova_v], ignore_index=True)):
                            st.session_state.entrada_lote = []
                            st.success("Salvo com sucesso!")
                            time.sleep(1); st.rerun()

    with st.expander("🗑️ Apagar Modelo"):
        if not df_est.empty:
            mod_apagar = st.selectbox("Modelo para REMOVER", sorted(df_est['Modelo'].unique()))
            if st.button("Confirmar Exclusão"):
                salvar("Estoque", df_est[df_est['Modelo'] != mod_apagar])
                st.rerun()

with tabs[1]: # NOVOS MODELOS
    with st.form("form_novo"):
        n_novo = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if n_novo:
                linha = {"Modelo": n_novo}
                linha.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar("Estoque", pd.concat([df_est, pd.DataFrame([linha])], ignore_index=True))
                st.rerun()

with tabs[2]: # VENDAS
    c1, c2 = st.columns(2)
    with c1:
        v_cl = st.selectbox("Cliente", sorted(list(df_cli['Nome'].unique())) + ["Avulso"]) if not df_cli.empty else st.selectbox("Cliente", ["Avulso"])
        v_mo = st.selectbox("Modelo ", sorted(df_est['Modelo'].unique())) if not df_est.empty else None
        v_ta = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_pr = st.number_input("Preço R$", min_value=0.0)
        v_qt = st.number_input("Qtd Vendida", min_value=1)
        if st.button("➕ Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mo, "Tam": v_ta, "Qtd": v_qt, "Pre": v_pr})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']}")
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            if st.button("🏁 Finalizar"):
                df_e = df_est.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    v_atu = int(float(df_e.at[idx, it['Tam']])) if df_e.at[idx, it['Tam']] != "" else 0
                    df_e.at[idx, it['Tam']] = v_atu - it['Qtd']
                salvar("Estoque", df_e)
                time.sleep(1)
                salvar("Pedidos", pd.concat([df_ped, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cl, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": "Pago"}])], ignore_index=True))
                st.session_state.cart = []; st.rerun()

with tabs[4]: # CLIENTES
    with st.form("form_cli"):
        cn = st.text_input("Nome"); cl = st.text_input("Loja"); cc = st.text_input("Cidade"); ct = st.text_input("Tel")
        if st.form_submit_button("Salvar"):
            salvar("Clientes", pd.concat([df_cli, pd.DataFrame([{"Nome": cn, "Loja": cl, "Cidade": cc, "Telefone": ct}])], ignore_index=True))
            st.rerun()
    st.dataframe(df_cli.sort_values(by="Nome"), hide_index=True)

with tabs[5]: # EXTRATO
    if not df_ped.empty:
        for idx, r in df_ped.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.1, 0.1, 0.8])
                if c1.button("🗑️", key=f"del_{idx}"):
                    salvar("Pedidos", df_ped.drop(idx))
                    st.rerun()
                c2.download_button("📄", gerar_recibo(r), f"doc_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Cliente']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

with tabs[6]: # LEMBRETES
    with st.form("form_lem"):
        ln = st.text_input("Nome"); ld = st.date_input("Vencimento"); lv = st.number_input("Valor R$")
        if st.form_submit_button("Agendar"):
            salvar("Lembretes", pd.concat([df_lem, pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Vencimento": str(ld), "Valor": lv}])], ignore_index=True))
            st.rerun()
    for idx, r in df_lem.iterrows():
        col1, col2 = st.columns([0.1, 0.9])
        if col1.button("✅", key=f"ok_{idx}"):
            salvar("Lembretes", df_lem.drop(idx))
            st.rerun()
        st.write(f"📌 **{r['Nome']}** - {r['Vencimento']} - R$ {r['Valor']}")
