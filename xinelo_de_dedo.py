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
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo do Pedido", "Valor Total"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"])
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
                    q = int(float(row[t])) if str(row[t]) != "" else 0
                    if q < 3: st.write(f"🔴 {mod} ({t}): {q}")
                    elif q < 5: st.write(f"🟡 {mod} ({t}): {q}")
                except: continue

# --- INTERFACE ---
st.title("🩴 Xinelo de Dedo - Gestão")
tab1, tab_cad, tab2, tab3, tab4 = st.tabs(["📊 Estoque", "✨ Cadastro Modelos", "🛒 Vendas", "👥 Clientes", "🧾 Extrato"])

# --- TAB 1: ESTOQUE E ENTRADA ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1.3, 2])
    with c1:
        st.subheader("📦 Entrada (Compra)")
        if not df_estoque.empty:
            m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="ent_mod")
            t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            col_q, col_v = st.columns(2)
            q_aq = col_q.number_input("Qtd", min_value=1, step=1, key="ent_q")
            v_uni = col_v.number_input("R$ Unit. (Compra)", min_value=0.0, format="%.2f", key="ent_v")
            if st.button("➕ Add Compra"):
                st.session_state.carrinho_ent.append({"Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, "Unitário": v_uni, "Subtotal": q_aq * v_uni})
            
            for i, item in enumerate(st.session_state.carrinho_ent):
                cd, cx = st.columns([0.08, 0.92])
                if cd.button("🗑️", key=f"de_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
                cx.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']} - **R$ {item['Subtotal']:.2f}**")
            
            if st.session_state.carrinho_ent:
                total_compra = sum(i['Subtotal'] for i in st.session_state.carrinho_ent)
                st.markdown(f"### Total: R$ {total_compra:.2f}")
                if st.button(f"✅ Confirmar Entrada", type="primary"):
                    df_e_new = df_estoque.copy()
                    res_f = []
                    for i in st.session_state.carrinho_ent:
                        idx = df_e_new.index[df_e_new['Modelo'] == i['Modelo']][0]
                        val_at = int(float(df_e_new.at[idx, i['Tamanho']])) if str(df_e_new.at[idx, i['Tamanho']]) != "" else 0
                        df_e_new.at[idx, i['Tamanho']] = val_at + i['Qtd']
                        res_f.append(f"{i['Modelo']}({i['Tamanho']}) x{i['Qtd']}")
                    
                    nova_aq = pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo da Carga": " | ".join(res_f), "Valor Total": total_compra}])], ignore_index=True)
                    atualizar_planilha("Estoque", df_e_new)
                    atualizar_planilha("Aquisicoes", nova_aq)
                    st.session_state.carrinho_ent = []
                    st.success("Entrada registada com sucesso!")
                    st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        for idx, row in df_estoque.iterrows():
            col_del, col_txt = st.columns([0.08, 0.92])
            if col_del.button("🗑️", key=f"ex_{idx}"): 
                atualizar_planilha("Estoque", df_estoque.drop(idx))
                st.success("Modelo removido!")
                st.rerun()
            col_txt.write(f"**{row['Modelo']}**")
        st.dataframe(df_estoque, hide_index=True)

# --- TAB 2: CADASTRO MODELOS ---
with tab_cad:
    with st.form("f_mod"):
        n_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if n_m: 
                ni = {"Modelo": n_m}; ni.update(ipts)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True))
                st.success(f"Modelo {n_m} cadastrado!")
                st.rerun()

# --- TAB 3: VENDAS ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        v_c = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["-"])
        v_m = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"])
        v_t = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        try: disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_m, v_t].values[0]))
        except: disp = 0
        st.metric("Estoque Disponível", disp)
        col_vq, col_vv = st.columns(2)
        v_q = col_vq.number_input("Qtd", min_value=0, max_value=max(0, disp), step=1)
        v_p = col_vv.number_input("R$ Unit. (Venda)", min_value=0.0, format="%.2f")
        if st.button("➕ Add Item"):
            if v_q > 0: 
                st.session_state.carrinho_v.append({"Modelo": v_m, "Tamanho": v_t, "Qtd": v_q, "Preço": v_p, "Subtotal": v_q * v_p})
                st.rerun()
    with c2:
        for idx, item in enumerate(st.session_state.carrinho_v):
            cd, ct = st.columns([0.1, 0.9])
            if cd.button("🗑️", key=f"dv_{idx}"): st.session_state.carrinho_v.pop(idx); st.rerun()
            ct.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']} - **R$ {item['Subtotal']:.2f}**")
        
        if st.session_state.carrinho_v:
            total_venda = sum(i['Subtotal'] for i in st.session_state.carrinho_v)
            st.markdown(f"### Total Venda: R$ {total_venda:.2f}")
            if st.button(f"🚀 Finalizar Pedido", type="primary"):
                df_ev = df_estoque.copy()
                res_v = []
                for it in st.session_state.carrinho_v:
                    ix = df_ev.index[df_ev['Modelo'] == it['Modelo']][0]
                    df_ev.at[ix, it['Tamanho']] = int(float(df_ev.at[ix, it['Tamanho']])) - it['Qtd']
                    res_v.append(f"{it['Modelo']}({it['Tamanho']} x{it['Qtd']})")
                
                nova_venda = pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_c, "Resumo do Pedido": " | ".join(res_v), "Valor Total": total_venda}])], ignore_index=True)
                atualizar_planilha("Estoque", df_ev)
                atualizar_planilha("Pedidos", nova_venda)
                st.session_state.carrinho_v = []
                st.success("Venda finalizada com sucesso!")
                st.rerun()

# --- TAB 4: CLIENTES ---
with tab3:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli"):
        col1, col2 = st.columns(2)
        n_c, l_c = col1.text_input("Nome"), col2.text_input("Loja")
        c_c, t_c = col1.text_input("Cidade"), col2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            if n_c:
                atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": c_c, "Telefone": t_c}])], ignore_index=True))
                st.success("Cliente guardado!")
                st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB 5: EXTRATO (COM FILTRO E MENSAGENS) ---
with tab4:
    st.subheader("🧾 Extrato de Movimentação")
    u = pd.concat([df_pedidos.assign(Tipo="🔴 SAÍDA"), df_aquisicoes.assign(Tipo="🟢 ENTRADA")], ignore_index=True)
    
    if not u.empty:
        u['Data_DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
        modo_filtro = col_f1.radio("Ver:", ["Mês Atual", "Tudo"], horizontal=True)
        
        if modo_filtro == "Mês Atual":
            meses = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}
            mes_sel = col_f2.selectbox("Mês", options=list(meses.keys()), format_func=lambda x: meses[x], index=datetime.now().month-1)
            ano_sel = col_f3.selectbox("Ano", options=range(2024, 2030), index=range(2024, 2030).index(datetime.now().year))
            f_df = u[(u['Data_DT'].dt.month == mes_sel) & (u['Data_DT'].dt.year == ano_sel)].copy()
        else:
            f_df = u.copy()
        
        # Formatação
        f_df['Descrição'] = f_df.apply(lambda r: f"{r['Cliente']}: {r['Resumo do Pedido']}" if r['Tipo'] == "🔴 SAÍDA" else r['Resumo da Carga'], axis=1)
        f_df['Valor Total'] = f_df['Valor Total'].apply(lambda x: f"R$ {pd.to_numeric(x, errors='coerce'):.2f}")
        
        st.dataframe(f_df.sort_values('Data_DT', ascending=False)[['Data', 'Tipo', 'Descrição', 'Valor Total']], use_container_width=True, hide_index=True)
        
        # Resumo Financeiro
        rec = pd.to_numeric(f_df[f_df['Tipo'] == "🔴 SAÍDA"]['Valor Total'].str.replace('R$ ', ''), errors='coerce').sum()
        des = pd.to_numeric(f_df[f_df['Tipo'] == "🟢 ENTRADA"]['Valor Total'].str.replace('R$ ', ''), errors='coerce').sum()
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("Vendas (Receita)", f"R$ {rec:.2f}")
        c_r2.metric("Compras (Despesa)", f"R$ {des:.2f}")
        c_r3.metric("Saldo", f"R$ {rec - des:.2f}", delta=float(rec-des))
    else:
        st.info("Nenhuma movimentação registada.")
