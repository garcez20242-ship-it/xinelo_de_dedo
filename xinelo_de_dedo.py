import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo", layout="wide", page_icon="🩴")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÃO DE DATA/HORA (FUSO -3) ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0)
                if df is None or df.empty: return pd.DataFrame(columns=colunas)
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                for col in colunas:
                    if col not in df.columns:
                        df[col] = 0 if col in TAMANHOS_PADRAO else ""
                return df
            except: return pd.DataFrame(columns=colunas)
        
        df_e = ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO)
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Telefone", "Cidade"])
        df_a = ler_aba("Aquisicoes", ["Data", "Resumo da Carga", "Valor Total"])
        return conn, df_e, df_p, df_c, df_a
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes = carregar_dados()

# --- ATUALIZAÇÃO SEGURA ---
def atualizar_planilha(aba, dataframe):
    try:
        df_save = dataframe.copy()
        df_save = df_save.loc[:, ~df_save.columns.str.contains('^Unnamed')]
        df_save = df_save.astype(str).replace('nan', '')
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_save)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚠️ Alertas de Estoque")
    if not df_estoque.empty:
        for _, row in df_estoque.iterrows():
            mod = row['Modelo']
            for t in TAMANHOS_PADRAO:
                try:
                    q = int(float(row[t])) if row[t] != "" else 0
                    if q < 3: st.write(f"🔴 {mod} ({t}): {q}")
                    elif q < 5: st.write(f"🟡 {mod} ({t}): {q}")
                except: continue

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo - Gestão")

tab1, tab_cad, tab2, tab3, tab4 = st.tabs([
    "📊 Estoque & Aquisição", "✨ Cadastro de Modelos", "🛒 Vendas", "👥 Clientes", "🧾 Extrato Unificado"
])

# --- TAB 1: ENTRADA E INVENTÁRIO (COM EXCLUSÃO) ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1.3, 2])
    
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        if not df_estoque.empty:
            m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="ent_mod")
            t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            col_q, col_v = st.columns(2)
            q_aq = col_q.number_input("Qtd", min_value=1, step=1, key="ent_q")
            v_uni = col_v.number_input("Valor Unit.", min_value=0.0, format="%.2f", key="ent_v")
            
            if st.button("➕ Adicionar", key="btn_add_ent"):
                st.session_state.carrinho_ent.append({
                    "Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, 
                    "Unitário": v_uni, "Subtotal": q_aq * v_uni
                })
            
            if st.session_state.carrinho_ent:
                for i, item in enumerate(st.session_state.carrinho_ent):
                    cx, cd = st.columns([4, 1])
                    cx.write(f"**{item['Modelo']}** ({item['Tamanho']}) x{item['Qtd']}")
                    if cd.button("🗑️", key=f"del_ent_car_{i}"):
                        st.session_state.carrinho_ent.pop(i); st.rerun()
                
                total_c = sum(i['Subtotal'] for i in st.session_state.carrinho_ent)
                st.write(f"**Total: R$ {total_c:.2f}**")
                if st.button("✅ Confirmar Entrada", type="primary"):
                    df_e_new = df_estoque.copy()
                    res_f = []
                    for i in st.session_state.carrinho_ent:
                        idx = df_e_new.index[df_e_new['Modelo'] == i['Modelo']][0]
                        val_at = int(float(df_e_new.at[idx, i['Tamanho']])) if df_e_new.at[idx, i['Tamanho']] != "" else 0
                        df_e_new.at[idx, i['Tamanho']] = val_at + i['Qtd']
                        res_f.append(f"{i['Modelo']}({i['Tamanho']}) x{i['Qtd']} [Un: R${i['Unitário']:.2f}]")
                    
                    nova_aq = pd.concat([df_aquisicoes, pd.DataFrame([{
                        "Data": get_data_hora(), "Resumo da Carga": " | ".join(res_f), "Valor Total": f"{total_c:.2f}"
                    }])], ignore_index=True)
                    
                    atualizar_planilha("Estoque", df_e_new); atualizar_planilha("Aquisicoes", nova_aq)
                    st.session_state.carrinho_ent = []; st.rerun()
        else: st.info("Cadastre modelos primeiro.")

    with c2:
        st.subheader("📋 Inventário (Apagar Modelos)")
        if not df_estoque.empty:
            for idx, row in df_estoque.iterrows():
                col_del, col_txt = st.columns([0.15, 5])
                if col_del.button("🗑️", key=f"excluir_mod_{idx}"):
                    df_estoque = df_estoque.drop(idx)
                    atualizar_planilha("Estoque", df_estoque); st.rerun()
                col_txt.write(f"**{row['Modelo']}**")
            st.write("---")
            st.dataframe(df_estoque, hide_index=True, use_container_width=True)

# --- TAB 2: CADASTRO DE MODELOS ---
with tab_cad:
    st.subheader("✨ Novos Modelos")
    with st.form("f_cad", clear_on_submit=True):
        n_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0, key=f"c_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar Modelo"):
            if n_m and n_m not in df_estoque['Modelo'].values:
                ni = {"Modelo": n_m}; ni.update(ipts)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.rerun()

# --- TAB 3: VENDAS (COM TRAVA E REMOÇÃO) ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Carrinho de Vendas")
        v_c = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["-"], key="v_cli")
        v_m = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"], key="v_mod")
        v_t = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
        try:
            disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_m, v_t].values[0]))
        except: disp = 0
        st.metric("Estoque Disponível", disp)
        v_q = st.number_input("Qtd", min_value=0, max_value=max(0, disp), step=1, key="v_q")
        if st.button("➕ Adicionar Pedido", key="v_add"):
            if v_q > 0:
                st.session_state.carrinho_v.append({"Modelo": v_m, "Tamanho": v_t, "Qtd": v_q})
                st.rerun()
    with c2:
        if st.session_state.carrinho_v:
            for idx, item in enumerate(st.session_state.carrinho_v):
                ct, cd = st.columns([4, 1])
                ct.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']}")
                if cd.button("🗑️", key=f"del_v_car_{idx}"):
                    st.session_state.carrinho_v.pop(idx); st.rerun()
            if st.button("🚀 Finalizar Venda", type="primary", key="fin_v"):
                df_ev = df_estoque.copy()
                res_v = []
                for it in st.session_state.carrinho_v:
                    ix = df_ev.index[df_ev['Modelo'] == it['Modelo']][0]
                    df_ev.at[ix, it['Tamanho']] = int(float(df_ev.at[ix, it['Tamanho']])) - it['Qtd']
                    res_v.append(f"{it['Modelo']}({it['Tamanho']} x{it['Qtd']})")
                n_p = pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_c, "Resumo do Pedido": " | ".join(res_v)}])], ignore_index=True)
                atualizar_planilha("Estoque", df_ev); atualizar_planilha("Pedidos", n_p)
                st.session_state.carrinho_v = []; st.rerun()

# --- TAB 4: CLIENTES (CADASTRO COMPLETO) ---
with tab3:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli"):
        col1, col2 = st.columns(2)
        n_c = col1.text_input("Nome do Cliente")
        l_c = col2.text_input("Loja / Cidade")
        t_c = col1.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            if n_c:
                nova_lista_c = pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Telefone": t_c}])], ignore_index=True)
                atualizar_planilha("Clientes", nova_lista_c); st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB 5: EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato de Movimentação")
    ev = df_pedidos.copy()
    ev['Tipo'], ev['Descrição'], ev['Total'] = "🔴 SAÍDA", ev['Cliente'] + ": " + ev['Resumo do Pedido'], "---"
    ea = df_aquisicoes.copy()
    ea['Tipo'], ea['Descrição'], ea['Total'] = "🟢 ENTRADA", ea['Resumo da Carga'], ea['Valor Total'].apply(lambda x: f"R$ {x}")
    u = pd.concat([ev[['Data', 'Tipo', 'Descrição', 'Total']], ea[['Data', 'Tipo', 'Descrição', 'Total']]], ignore_index=True)
    if not u.empty:
        u['DS'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        st.dataframe(u.sort_values('DS', ascending=False).drop('DS', axis=1), use_container_width=True, hide_index=True)
