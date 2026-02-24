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
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0).dropna(how='all')
                if df is None or df.empty: return pd.DataFrame(columns=colunas)
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
        st.error(f"Erro ao conectar: {e}")
        return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes = carregar_dados()

# --- ATUALIZAÇÃO COM LIMPEZA DE CACHE ---
def atualizar_planilha(aba, dataframe):
    try:
        # Garante que números sejam salvos como strings formatadas para evitar erros de leitura
        df_limpo = dataframe.astype(str)
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_limpo)
        # LIMPA O CACHE PARA FORÇAR A LEITURA DOS NOVOS DADOS
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar na aba {aba}: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚠️ Alertas de Estoque")
    if not df_estoque.empty:
        criticos, atencao = [], []
        for _, row in df_estoque.iterrows():
            mod = row['Modelo']
            for t in TAMANHOS_PADRAO:
                try:
                    q = int(float(row[t])) # Uso de float antes de int previne erro com decimais
                    if q < 3: criticos.append(f"🔴 {mod} ({t}): {q}")
                    elif q < 5: atencao.append(f"🟡 {mod} ({t}): {q}")
                except: continue
        if criticos: 
            st.subheader("🚨 Crítico (<3)")
            for item in criticos: st.write(item)
        if atencao:
            st.subheader("⚠️ Atenção (<5)")
            for item in atencao: st.write(item)
        if not criticos and not atencao: st.success("Estoque em dia!")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo - Sistema de Gestão")

tab1, tab_cad, tab2, tab3, tab4 = st.tabs([
    "📊 Estoque & Aquisição", "✨ Cadastro de Modelos", "🛒 Vendas", "👥 Clientes", "🧾 Extrato Unificado"
])

# --- ABA 1: ESTOQUE E ENTRADA ---
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
            v_uni = col_v.number_input("Valor Unit. (R$)", min_value=0.0, format="%.2f", key="ent_v")
            v_subtotal = q_aq * v_uni
            st.info(f"Subtotal: R$ {v_subtotal:.2f}")
            
            if st.button("➕ Adicionar à Carga", key="btn_ent_add"):
                st.session_state.carrinho_ent.append({
                    "Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, 
                    "Unitário": v_uni, "Subtotal": v_subtotal
                })
            
            if st.session_state.carrinho_ent:
                st.write("---")
                for i, item in enumerate(st.session_state.carrinho_ent):
                    col_t, col_d = st.columns([4, 1])
                    col_t.write(f"**{item['Modelo']}** ({item['Tamanho']}) - {item['Qtd']}un")
                    if col_d.button("🗑️", key=f"del_ent_{i}"):
                        st.session_state.carrinho_ent.pop(i)
                        st.rerun()
                
                total_carga = sum(i['Subtotal'] for i in st.session_state.carrinho_ent)
                st.write(f"**Total da Carga: R$ {total_carga:.2f}**")
                if st.button("✅ Confirmar Tudo", key="ent_confirm", type="primary"):
                    resumo_f = []
                    # Criamos uma cópia para trabalhar os dados
                    estoque_atualizado = df_estoque.copy()
                    for item in st.session_state.carrinho_ent:
                        idx = estoque_atualizado.index[estoque_atualizado['Modelo'] == item['Modelo']][0]
                        # Soma o novo valor ao estoque atual
                        val_atual = int(float(estoque_atualizado.at[idx, item['Tamanho']]))
                        estoque_atualizado.at[idx, item['Tamanho']] = val_atual + item['Qtd']
                        resumo_f.append(f"{item['Modelo']}({item['Tamanho']}) x{item['Qtd']} [Un: R${item['Unitário']:.2f}]")
                    
                    nova_aq = pd.concat([df_aquisicoes, pd.DataFrame([{
                        "Data": get_data_hora(), 
                        "Resumo da Carga": " | ".join(resumo_f), 
                        "Valor Total": f"{total_carga:.2f}"
                    }])], ignore_index=True)
                    
                    atualizar_planilha("Estoque", estoque_atualizado)
                    atualizar_planilha("Aquisicoes", nova_aq)
                    st.session_state.carrinho_ent = []
                    st.success("Estoque Atualizado!")
                    st.rerun()
        else: st.info("Cadastre modelos primeiro.")
    with c2:
        st.subheader("📋 Inventário Atual")
        st.dataframe(df_estoque, hide_index=True, use_container_width=True)

# --- ABA 2: CADASTRO DE MODELOS ---
with tab_cad:
    st.subheader("✨ Novos Modelos")
    with st.form("f_novo", clear_on_submit=True):
        n_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0, key=f"cad_{t}") for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar Modelo"):
            if n_m and n_m not in df_estoque['Modelo'].values:
                ni = {"Modelo": n_m}; ni.update(ipts)
                novo_df_estoque = pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)
                atualizar_planilha("Estoque", novo_df_estoque); st.rerun()

# --- ABA 3: VENDAS ---
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
        
        st.metric("Disponível", disp)
        v_q = st.number_input("Quantidade", min_value=0, max_value=max(0, disp), step=1, key="v_qtd_val")
        
        if st.button("➕ Adicionar", key="v_add"):
            if v_q > 0:
                st.session_state.carrinho_v.append({"Modelo": v_m, "Tamanho": v_t, "Qtd": v_q})
                st.rerun()
    with c2:
        if st.session_state.carrinho_v:
            for idx, item in enumerate(st.session_state.carrinho_v):
                ct, cd = st.columns([4, 1])
                ct.write(f"{item['Modelo']} ({item['Tamanho']}) - {item['Qtd']} un")
                if cd.button("🗑️", key=f"del_v_{idx}"):
                    st.session_state.carrinho_v.pop(idx); st.rerun()
            if st.button("🚀 Finalizar Venda", type="primary"):
                est_v = df_estoque.copy()
                res_v = []
                for it in st.session_state.carrinho_v:
                    idx = est_v.index[est_v['Modelo'] == it['Modelo']][0]
                    est_v.at[idx, it['Tamanho']] = int(float(est_v.at[idx, it['Tamanho']])) - it['Qtd']
                    res_v.append(f"{it['Modelo']}({it['Tamanho']} x{it['Qtd']})")
                n_ped = pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_c, "Resumo do Pedido": " | ".join(res_v)}])], ignore_index=True)
                atualizar_planilha("Estoque", est_v); atualizar_planilha("Pedidos", n_ped)
                st.session_state.carrinho_v = []; st.rerun()

# --- ABA 4: CLIENTES ---
with tab3:
    with st.form("f_cli"):
        n, l = st.text_input("Nome"), st.text_input("Loja")
        if st.form_submit_button("Salvar Cliente"):
            n_cli = pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l}])], ignore_index=True)
            atualizar_planilha("Clientes", n_cli); st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- ABA 5: EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato Unificado")
    ext_v = df_pedidos.copy()
    ext_v['Tipo'], ext_v['Descrição'], ext_v['Total'] = "🔴 SAÍDA", ext_v['Cliente'] + ": " + ext_v['Resumo do Pedido'], "---"
    ext_a = df_aquisicoes.copy()
    ext_a['Tipo'], ext_a['Descrição'], ext_a['Total'] = "🟢 ENTRADA", ext_a['Resumo da Carga'], ext_a['Valor Total'].apply(lambda x: f"R$ {x}")
    ext_u = pd.concat([ext_v[['Data', 'Tipo', 'Descrição', 'Total']], ext_a[['Data', 'Tipo', 'Descrição', 'Total']]], ignore_index=True)
    if not ext_u.empty:
        ext_u['DS'] = pd.to_datetime(ext_u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        st.dataframe(ext_u.sort_values('DS', ascending=False).drop('DS', axis=1), use_container_width=True, hide_index=True)
