import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo", layout="wide", page_icon="🩴")

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

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'XINELO DE DEDO - RELATORIO DETALHADO', 0, 1, 'C')
        self.ln(10)

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
                    if col not in df.columns: df[col] = 0 if col in TAMANHOS_PADRAO else ""
                return df
            except: return pd.DataFrame(columns=colunas)
        
        return conn, \
               ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO), \
               ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]), \
               ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]), \
               ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"]), \
               ler_aba("Insumos", ["Data", "Descricao", "Valor"]), \
               ler_aba("Lembretes", ["Nome", "Data", "Valor"])
    except: return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos, df_lembretes = carregar_dados()

def atualizar_planilha(aba, dataframe):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
    st.cache_data.clear()

# --- BARRA LATERAL: ALERTAS ---
with st.sidebar:
    st.header("💳 Alertas de Pagamento")
    hoje = datetime.now().date()
    tem_pagamento = False
    if not df_lembretes.empty:
        df_l_temp = df_lembretes.copy()
        # Tenta ler formato BR ou ISO para comparação
        df_l_temp['Data_DT'] = pd.to_datetime(df_l_temp['Data'], dayfirst=True, errors='coerce').dt.date
        pendentes = df_l_temp[df_l_temp['Data_DT'] <= hoje]
        for _, row in pendentes.iterrows():
            st.error(f"**{row['Nome']}**\nVencimento: {row['Data']}\nValor: R$ {limpar_valor(row['Valor']):.2f}")
            tem_pagamento = True
    if not tem_pagamento:
        st.success("✅ Nenhum pagamento para hoje!")
    
    st.divider()

    st.header("⚠️ Alertas de Estoque")
    alerta_vazio = True
    if not df_estoque.empty:
        for _, row in df_estoque.iterrows():
            for tam in TAMANHOS_PADRAO:
                qtd = int(float(row[tam])) if str(row[tam]) != "" else 0
                if 0 < qtd <= 3:
                    st.warning(f"**{row['Modelo']}**\nTam: {tam} | Qtd: {qtd}")
                    alerta_vazio = False
                elif qtd == 0:
                    st.error(f"**{row['Modelo']}**\nTam: {tam} | ESGOTADO")
                    alerta_vazio = False
    if alerta_vazio:
        st.success("✅ Estoque em dia!")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo - Gestão Pro")

tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

# --- TAB 1: ESTOQUE ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1.3, 2])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"], key="sel_mod_est")
        t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_tam_est")
        col_q, col_v = st.columns(2)
        q_aq = col_q.number_input("Qtd", min_value=1, step=1, key="num_q_est")
        v_uni = col_v.number_input("R$ Unit. Compra", min_value=0.0, format="%.2f", key="num_v_est")
        if st.button("➕ Add Compra", key="btn_add_est"):
            st.session_state.carrinho_ent.append({"Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, "Unit": v_uni, "Sub": q_aq*v_uni})
            st.rerun()
        for i, item in enumerate(st.session_state.carrinho_ent):
            cl_del, cl_txt = st.columns([0.08, 0.92])
            if cl_del.button("🗑️", key=f"de_ent_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
            cl_txt.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']} - **R$ {item['Sub']:.2f}**")
        if st.session_state.carrinho_ent:
            total_c = sum(it['Sub'] for it in st.session_state.carrinho_ent)
            if st.button(f"✅ Confirmar R$ {total_c:.2f}", type="primary", key="btn_conf_est"):
                df_e_new = df_estoque.copy()
                res_f = []
                for it in st.session_state.carrinho_ent:
                    idx = df_e_new.index[df_e_new['Modelo'] == it['Modelo']][0]
                    val = int(float(df_e_new.at[idx, it['Tamanho']])) if str(df_e_new.at[idx, it['Tamanho']]) != "" else 0
                    df_e_new.at[idx, it['Tamanho']] = val + it['Qtd']
                    res_f.append(f"{it['Modelo']}({it['Tamanho']})x{it['Qtd']}")
                atualizar_planilha("Estoque", df_e_new)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_f), "Valor Total": total_c}])], ignore_index=True))
                st.session_state.carrinho_ent = []; st.success("Entrada realizada!"); st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        for idx, row in df_estoque.iterrows():
            cl_del, cl_txt = st.columns([0.08, 0.92])
            if cl_del.button("🗑️", key=f"ex_mod_inv_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
            cl_txt.write(f"**{row['Modelo']}**")
        st.dataframe(df_estoque, hide_index=True)

# --- TAB CADASTRO ---
with tab_cad:
    st.subheader("✨ Cadastrar Novo Modelo")
    with st.form("f_cad_mod"):
        n_m = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Finalizar Cadastro"):
            if n_m:
                ni = {"Modelo": n_m}; ni.update(ipts)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.success("Cadastrado!"); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique(), key="s_cli_v") if not df_clientes.empty else st.text_input("Cliente", key="i_cli_v")
        v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="s_mod_v")
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="s_tam_v")
        disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0])) if not df_estoque.empty else 0
        st.metric("Disponível", disp)
        v_qtd = st.number_input("Qtd", min_value=0, max_value=disp, step=1, key="n_qtd_v")
        v_pre = st.number_input("R$ Unit. Venda", min_value=0.0, format="%.2f", key="n_pre_v")
        if st.button("➕ Add Item", key="b_add_v"):
            if v_qtd > 0:
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Preco": v_pre, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        st.subheader("📄 Carrinho de Venda")
        for idx, it in enumerate(st.session_state.carrinho_v):
            cl_d, cl_t = st.columns([0.1, 0.9])
            if cl_d.button("🗑️", key=f"dv_v_{idx}"): st.session_state.carrinho_v.pop(idx); st.rerun()
            cl_t.write(f"{it['Mod']} ({it['Tam']}) x{it['Qtd']} - **R$ {it['Sub']:.2f}**")
        if st.session_state.carrinho_v:
            tot_v = sum(i['Sub'] for i in st.session_state.carrinho_v)
            st.markdown(f"### Total: R$ {tot_v:.2f}")
            st_pg = st.selectbox("Status", ["Pago", "Pendente"], key="s_pg_v")
            fm_pg = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "Boleto"], key="f_pg_v")
            if st.button("🚀 Finalizar Pedido", type="primary", key="b_fin_v"):
                df_ev = df_estoque.copy()
                res_v = " | ".join([f"{it['Mod']}({it['Tam']}x{it['Qtd']})" for it in st.session_state.carrinho_v])
                for it in st.session_state.carrinho_v:
                    ix = df_ev.index[df_ev['Modelo'] == it['Mod']][0]
                    df_ev.at[ix, it['Tam']] = int(float(df_ev.at[ix, it['Tam']])) - it['Qtd']
                atualizar_planilha("Estoque", df_ev)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": res_v, "Valor Total": tot_v, "Status Pagto": st_pg, "Forma": fm_pg}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.success("Venda realizada!"); st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    st.subheader("🛠️ Gastos com Insumos")
    with st.form("f_ins_novo"):
        desc_i = st.text_input("Descrição do Gasto")
        val_i = st.number_input("Valor R$", min_value=0.0, format="%.2f")
        if st.form_submit_button("Salvar Gasto"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])], ignore_index=True))
            st.rerun()
    for idx, row in df_insumos.iterrows():
        cl_del, cl_txt = st.columns([0.08, 0.92])
        if cl_del.button("🗑️", key=f"ex_ins_list_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        cl_txt.write(f"{row['Data']} - {row['Descricao']} - **R$ {limpar_valor(row['Valor']):.2f}**")

# --- TAB CLIENTES ---
with tab3:
    st.subheader("👥 Clientes")
    with st.form("f_cli"):
        c1, c2 = st.columns(2)
        n_c, l_c = c1.text_input("Nome"), c2.text_input("Loja")
        ci_c, t_c = c1.text_input("Cidade"), c2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": ci_c, "Telefone": t_c}])], ignore_index=True))
            st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB 4: EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato Financeiro")
    p_ext = df_pedidos.assign(Origem="Pedidos", Tipo="🔴 Venda")
    a_ext = df_aquisicoes.assign(Origem="Aquisicoes", Tipo="🟢 Compra")
    i_ext = df_insumos.assign(Origem="Insumos", Tipo="🟠 Insumo").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p_ext, a_ext, i_ext], ignore_index=True)
    ver_tudo = st.checkbox("Exibir Histórico Completo", key="check_ver_tudo")
    if not u.empty:
        u['Data_DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        if not ver_tudo:
            u = u[(u['Data_DT'].dt.month == datetime.now().month) & (u['Data_DT'].dt.year == datetime.now().year)]
        u = u.sort_values('Data_DT', ascending=False)
    if u.empty:
        st.info("ℹ️ Nenhuma movimentação registrada para este período.")
        vendas, gastos = 0.0, 0.0
    else:
        for idx, row in u.iterrows():
            col_del, col_info = st.columns([0.08, 0.92])
            if col_del.button("🗑️", key=f"del_ext_{idx}"):
                if row['Origem'] == "Pedidos":
                    atualizar_planilha("Pedidos", df_pedidos[~((df_pedidos['Data'] == row['Data']) & (df_pedidos['Cliente'] == row['Cliente']))])
                elif row['Origem'] == "Aquisicoes":
                    atualizar_planilha("Aquisicoes", df_aquisicoes[~((df_aquisicoes['Data'] == row['Data']) & (df_aquisicoes['Resumo'] == row['Resumo']))])
                elif row['Origem'] == "Insumos":
                    atualizar_planilha("Insumos", df_insumos[~((df_insumos['Data'] == row['Data']) & (df_insumos['Descricao'] == row['Resumo']))])
                st.rerun()
            val_num = limpar_valor(row['Valor Total'])
            txt_resumo = f"{row['Cliente']}: {row['Resumo']}" if row['Origem'] == "Pedidos" else row['Resumo']
            col_info.write(f"**{row['Data']}** | {row['Tipo']} | {txt_resumo} | **R$ {val_num:.2f}**")
        vendas = u[u['Origem'] == "Pedidos"]['Valor Total'].apply(limpar_valor).sum()
        gastos = u[u['Origem'].isin(["Aquisicoes", "Insumos"])]['Valor Total'].apply(limpar_valor).sum()
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Vendas", f"R$ {vendas:.2f}")
    c2.metric("Saídas", f"R$ {gastos:.2f}")
    c3.metric("Saldo", f"R$ {vendas - gastos:.2f}")
    
    # BOTAO PARA PDF DE EXTRATO (ADICIONADO)
    if not u.empty:
        if st.button("📄 Gerar PDF Detalhado"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, f"RELATORIO FINANCEIRO - Saldo: R$ {vendas-gastos:.2f}", ln=True)
            pdf.ln(5)
            for _, r in u.iterrows():
                pdf.set_font('Arial', '', 10)
                pdf.cell(0, 8, f"{r['Data']} | {r['Tipo']} | R$ {limpar_valor(r['Valor Total']):.2f}", ln=True)
            st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="extrato.pdf")

# --- TAB 5: LEMBRETES ---
with tab5:
    st.subheader("📅 Agendar Lembrete de Pagamento")
    with st.form("f_lembrete"):
        l_nome = st.text_input("Nome do Lembrete (ex: Aluguel, Fornecedor X)")
        col_d, col_v = st.columns(2)
        # Campo de data no formato dia/mês/ano para o usuário
        l_data = col_d.date_input("Data de Pagamento", format="DD/MM/YYYY")
        l_valor = col_v.number_input("Valor R$", min_value=0.0, format="%.2f")
        if st.form_submit_button("Salvar Lembrete"):
            # Salva na planilha já formatado em dia/mês/ano
            novo_l = pd.DataFrame([{"Nome": l_nome, "Data": l_data.strftime("%d/%m/%Y"), "Valor": l_valor}])
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, novo_l], ignore_index=True))
            st.success("Lembrete agendado!"); st.rerun()
    st.markdown("---")
    st.subheader("📌 Meus Lembretes")
    if not df_lembretes.empty:
        for idx, row in df_lembretes.iterrows():
            c_del, c_info = st.columns([0.08, 0.92])
            if c_del.button("🗑️", key=f"del_lem_{idx}"):
                atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
            c_info.write(f"**{row['Nome']}** - Vence em: {row['Data']} - **R$ {limpar_valor(row['Valor']):.2f}**")
    else: st.info("Nenhum lembrete cadastrado.")
