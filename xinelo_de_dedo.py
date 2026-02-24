import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v7.6", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Master v7.6 - Estabilidade e Pesquisa")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- CONEXÃO E SEGURANÇA ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        return float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except: return 0.0

@st.cache_data(ttl=2)
def carregar_dados():
    abas = ["Estoque", "Pedidos", "Clientes", "Insumos", "Lembretes"]
    leitura = {}
    for aba in abas:
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                if aba == "Estoque": df = df.sort_values(by="Modelo")
                leitura[aba] = df
            else: leitura[aba] = pd.DataFrame()
        except: leitura[aba] = pd.DataFrame()
    return leitura

def salvar_seguro(aba, df_novo):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        time.sleep(1) # Tempo para o Google processar
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

d = carregar_dados()
df_est, df_ped, df_cli, df_ins, df_lem = d["Estoque"], d["Pedidos"], d["Clientes"], d["Insumos"], d["Lembretes"]

# --- INTERFACE ---
tabs = st.tabs(["📊 Estoque", "✨ Novos Modelos", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário")
    
    # PESQUISA RÁPIDA
    busca = st.text_input("🔍 Pesquisar por Modelo", "", key="busca_estoque").strip().lower()
    df_f = df_est[df_est['Modelo'].str.lower().str.contains(busca)] if busca else df_est
    st.dataframe(df_f, hide_index=True, use_container_width=True)
    
    with st.expander("➕ Entrada de Compra Multi-Modelo"):
        if 'entrada_lote' not in st.session_state: st.session_state.entrada_lote = []
        c1, c2, c3 = st.columns(3)
        mod_e = c1.selectbox("Modelo", sorted(df_est['Modelo'].unique()), key="sel_ent_mod")
        tam_e = c2.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_ent_tam")
        qtd_e = c3.number_input("Qtd", min_value=1, key="num_ent_qtd")
        
        if st.button("Adicionar ao Lote"):
            st.session_state.entrada_lote.append({"Modelo": mod_e, "Tam": tam_e, "Qtd": qtd_e})
            st.rerun()
            
        if st.session_state.entrada_lote:
            st.table(st.session_state.entrada_lote)
            val_total = st.number_input("Valor Geral da Compra (R$)", min_value=0.0, key="val_geral_compra")
            if st.button("🏁 Finalizar e Registrar Tudo", type="primary"):
                with st.spinner("Salvando..."):
                    df_atu = df_est.copy()
                    resumo = []
                    for item in st.session_state.entrada_lote:
                        idx = df_atu.index[df_atu['Modelo'] == item['Modelo']][0]
                        atual = int(float(df_atu.at[idx, item['Tam']])) if df_atu.at[idx, item['Tam']] != "" else 0
                        df_atu.at[idx, item['Tam']] = atual + item['Qtd']
                        resumo.append(f"{item['Modelo']}({item['Tam']}x{item['Qtd']})")
                    
                    if salvar_seguro("Estoque", df_atu):
                        nova_m = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "FORNECEDOR", "Resumo": f"COMPRA: {' | '.join(resumo)}", "Valor Total": val_total, "Status Pagto": "Pago"}])
                        salvar_seguro("Pedidos", pd.concat([df_ped, nova_m], ignore_index=True))
                        st.session_state.entrada_lote = []
                        st.success("Estoque e Extrato atualizados!")
                        time.sleep(1); st.rerun()

    with st.expander("🗑️ Apagar Modelo"):
        mod_del = st.selectbox("Escolha o modelo para remover", sorted(df_est['Modelo'].unique()), key="sel_del_mod")
        if st.button("Remover Permanentemente"):
            if salvar_seguro("Estoque", df_est[df_est['Modelo'] != mod_del]):
                st.rerun()

with tabs[1]: # NOVOS MODELOS
    st.subheader("✨ Cadastro")
    nome_n = st.text_input("Nome do Chinelo", key="input_cad_novo")
    if st.button("Gravar no Sistema"):
        if nome_n and nome_n not in df_est['Modelo'].values:
            linha = {"Modelo": nome_n}
            linha.update({t: 0 for t in TAMANHOS_PADRAO})
            if salvar_seguro("Estoque", pd.concat([df_est, pd.DataFrame([linha])], ignore_index=True)):
                st.success("Modelo cadastrado!"); time.sleep(1); st.rerun()
        else: st.error("Nome vazio ou já existente.")

with tabs[2]: # VENDAS
    c1, c2 = st.columns(2)
    with c1:
        v_cl = st.selectbox("Cliente", sorted(list(df_cli['Nome'].unique())) + ["Avulso"], key="sel_vend_cli")
        v_mo = st.selectbox("Modelo", sorted(df_est['Modelo'].unique()), key="sel_vend_mod")
        v_ta = st.selectbox("Tam", TAMANHOS_PADRAO, key="sel_vend_tam")
        v_pr = st.number_input("Preço Unitário R$", min_value=0.0, key="num_vend_pr")
        v_qt = st.number_input("Qtd Vendida", min_value=1, key="num_vend_qtd")
        if st.button("➕ Carrinho"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mo, "Tam": v_ta, "Qtd": v_qt, "Pre": v_pr})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            total, itens = 0, []
            for it in st.session_state.cart:
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']}")
                total += (it['Pre'] * it['Qtd']); itens.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            if st.button("🏁 Finalizar Venda"):
                df_e = df_est.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                if salvar_seguro("Estoque", df_e):
                    salvar_seguro("Pedidos", pd.concat([df_ped, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cl, "Resumo": " | ".join(itens), "Valor Total": total, "Status Pagto": "Pago"}])], ignore_index=True))
                    st.session_state.cart = []; st.success("Venda registrada!"); time.sleep(1); st.rerun()

with tabs[4]: # CLIENTES
    with st.form("f_clientes"):
        n, l, c, t = st.text_input("Nome"), st.text_input("Loja"), st.text_input("Cidade"), st.text_input("Tel")
        if st.form_submit_button("Salvar Cliente"):
            if salvar_seguro("Clientes", pd.concat([df_cli, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": c, "Telefone": t}])], ignore_index=True)):
                st.rerun()
    st.dataframe(df_cli.sort_values(by="Nome"), hide_index=True)

with tabs[5]: # EXTRATO
    if not df_ped.empty:
        for idx, r in df_ped.sort_index(ascending=False).iterrows():
            with st.container(border=True):
                st.write(f"**{r['Data']}** | {r['Cliente']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")
                st.caption(f"Conteúdo: {r['Resumo']}")
                if st.button("🗑️ Excluir Registro", key=f"del_ext_{idx}"):
                    if salvar_seguro("Pedidos", df_ped.drop(idx)): st.rerun()

with tabs[6]: # LEMBRETES
    with st.form("f_lembrete"):
        nom, ven, val = st.text_input("Título"), st.date_input("Vencimento"), st.number_input("Valor R$")
        if st.form_submit_button("Agendar"):
            if salvar_seguro("Lembretes", pd.concat([df_lem, pd.DataFrame([{"Data": get_data_hora(), "Nome": nom, "Vencimento": str(ven), "Valor": val}])], ignore_index=True)):
                st.rerun()
    for idx, r in df_lem.iterrows():
        if st.button(f"✅ Concluir {r['Nome']}", key=f"ok_lem_{idx}"):
            if salvar_seguro("Lembretes", df_lem.drop(idx)): st.rerun()
