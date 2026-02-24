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

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Xinelo de Dedo - Relatorio Financeiro', 0, 1, 'C')
        self.ln(5)

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
        df_p = ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"])
        df_c = ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"])
        df_a = ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"])
        df_i = ler_aba("Insumos", ["Data", "Descricao", "Valor"])
        return conn, df_e, df_p, df_c, df_a, df_i
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos = carregar_dados()

def atualizar_planilha(aba, dataframe):
    try:
        df_save = dataframe.copy()
        df_save = df_save.loc[:, ~df_save.columns.str.contains('^Unnamed')]
        df_save = df_save.astype(str).replace('nan', '')
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_save)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Xinelo de Dedo - Gestão Pro")
tab1, tab_cad, tab2, tab_ins, tab3, tab4 = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato & PDF"])

# --- TAB 1: ESTOQUE (COM LIXEIRA MINI) ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1.3, 2])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        if not df_estoque.empty:
            m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="ent_mod")
            t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            col_q, col_v = st.columns(2)
            q_aq = col_q.number_input("Qtd", min_value=1, step=1)
            v_uni = col_v.number_input("R$ Unit. Compra", min_value=0.0, format="%.2f")
            if st.button("➕ Add Compra"):
                st.session_state.carrinho_ent.append({"Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, "Unit": v_uni, "Sub": q_aq*v_uni})
            
            for i, item in enumerate(st.session_state.carrinho_ent):
                cl_del, cl_txt = st.columns([0.08, 0.92])
                if cl_del.button("🗑️", key=f"de_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
                cl_txt.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']} - **R$ {item['Sub']:.2f}**")
            
            if st.session_state.carrinho_ent:
                total_c = sum(it['Sub'] for it in st.session_state.carrinho_ent)
                st.markdown(f"### Total: R$ {total_c:.2f}")
                if st.button("✅ Confirmar Entrada", type="primary"):
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
            if cl_del.button("🗑️", key=f"ex_mod_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
            cl_txt.write(f"**{row['Modelo']}**")
        st.dataframe(df_estoque, hide_index=True)

# --- TAB CADASTRO ---
with tab_cad:
    with st.form("f_cad"):
        n_m = st.text_input("Novo Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if n_m:
                ni = {"Modelo": n_m}; ni.update(ipts)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.success("Cadastrado!"); st.rerun()

# --- TAB 2: VENDAS (TRAVA ESTOQUE + PAGAMENTO) ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique()) if not df_clientes.empty else st.text_input("Cliente")
        v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
        try: disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
        except: disp = 0
        st.metric("Disponível", disp)
        col_q, col_p = st.columns(2)
        v_qtd = col_q.number_input("Qtd", min_value=0, max_value=disp, step=1)
        v_pre = col_p.number_input("R$ Unit. Venda", min_value=0.0, format="%.2f")
        if st.button("➕ Add Item"):
            if v_qtd > 0:
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Preco": v_pre, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        for idx, it in enumerate(st.session_state.carrinho_v):
            cl_d, cl_t = st.columns([0.1, 0.9])
            if cl_d.button("🗑️", key=f"dv_{idx}"): st.session_state.carrinho_v.pop(idx); st.rerun()
            cl_t.write(f"{it['Mod']} ({it['Tam']}) x{it['Qtd']} - **R$ {it['Sub']:.2f}**")
        if st.session_state.carrinho_v:
            tot_v = sum(i['Sub'] for i in st.session_state.carrinho_v)
            st.markdown(f"### Total: R$ {tot_v:.2f}")
            col_s, col_f = st.columns(2)
            st_pg = col_s.selectbox("Status", ["Pago", "Pendente"])
            fm_pg = col_f.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "Boleto"])
            if st.button("🚀 Finalizar Pedido", type="primary"):
                df_ev = df_estoque.copy()
                res_v = []
                for it in st.session_state.carrinho_v:
                    ix = df_ev.index[df_ev['Modelo'] == it['Mod']][0]
                    df_ev.at[ix, it['Tam']] = int(float(df_ev.at[ix, it['Tam']])) - it['Qtd']
                    res_v.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
                atualizar_planilha("Estoque", df_ev)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res_v), "Valor Total": tot_v, "Status Pagto": st_pg, "Forma": fm_pg}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.success("Venda realizada!"); st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    st.subheader("🛠️ Gastos com Insumos")
    with st.form("f_ins"):
        desc_i = st.text_input("Descrição (Sacolas, Linhas, etc)")
        val_i = st.number_input("Valor R$", min_value=0.0, format="%.2f")
        if st.form_submit_button("Salvar Gasto"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])], ignore_index=True))
            st.success("Gasto salvo!"); st.rerun()
    for idx, row in df_insumos.iterrows():
        cl_del, cl_txt = st.columns([0.08, 0.92])
        if cl_del.button("🗑️", key=f"ex_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        cl_txt.write(f"{row['Data']} - {row['Descricao']} - **R$ {float(row['Valor']):.2f}**")

# --- TAB CLIENTES (LOJA/CIDADE SEPARADOS) ---
with tab3:
    with st.form("f_cli"):
        c1, c2 = st.columns(2)
        n_c = c1.text_input("Nome")
        l_c = c2.text_input("Loja")
        ci_c = c1.text_input("Cidade")
        t_c = c2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": ci_c, "Telefone": t_c}])], ignore_index=True)); st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB EXTRATO & PDF ---
with tab4:
    st.subheader("🧾 Extrato Financeiro")
    u = pd.concat([
        df_pedidos.assign(Tipo="🔴 SAÍDA (Venda)"),
        df_aquisicoes.assign(Tipo="🟢 ENTRADA (Compra)"),
        df_insumos.assign(Tipo="🟠 INSUMO").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    ], ignore_index=True)
    
    if not u.empty:
        u['Data_DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        filt = st.radio("Filtro:", ["Mês Atual", "Tudo"], horizontal=True)
        if filt == "Mês Atual":
            u = u[(u['Data_DT'].dt.month == datetime.now().month) & (u['Data_DT'].dt.year == datetime.now().year)]
        
        exibir = u.sort_values('Data_DT', ascending=False).copy()
        exibir['Valor Total'] = exibir['Valor Total'].apply(lambda x: f"R$ {pd.to_numeric(x, errors='coerce'):.2f}")
        st.dataframe(exibir[['Data', 'Tipo', 'Resumo', 'Valor Total', 'Status Pagto']], use_container_width=True, hide_index=True)
        
        # RESUMO CARDS
        vendas = pd.to_numeric(u[u['Tipo'].str.contains("SAÍDA")]['Valor Total'], errors='coerce').sum()
        custos = pd.to_numeric(u[u['Tipo'].str.contains("ENTRADA")]['Valor Total'], errors='coerce').sum()
        insum = pd.to_numeric(u[u['Tipo'].str.contains("INSUMO")]['Valor Total'], errors='coerce').sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Vendas", f"R$ {vendas:.2f}")
        c2.metric("Custos (Compras+Insumos)", f"R$ {custos+insum:.2f}")
        c3.metric("Lucro", f"R$ {vendas - custos - insum:.2f}")

        # PDF SIMPLIFICADO
        if st.button("📄 Gerar Relatório PDF"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 10, f"Periodo: {filt}", ln=True)
            pdf.cell(0, 10, f"Lucro Bruto: R$ {vendas-custos-insum:.2f}", ln=True)
            st.download_button("Clique para Baixar", data=pdf.output(dest='S').encode('latin-1'), file_name="relatorio.pdf")
