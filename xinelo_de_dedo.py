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
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'XINELO DE DEDO - RELATORIO DETALHADO', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Gerado em: {get_data_hora()}', 0, 1, 'C')
        self.ln(10)

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 8, label, 0, 1, 'L', 1)
        self.ln(4)

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
        
        return conn, ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO), \
               ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]), \
               ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]), \
               ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"]), \
               ler_aba("Insumos", ["Data", "Descricao", "Valor"])
    except: return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos = carregar_dados()

def atualizar_planilha(aba, dataframe):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
    st.cache_data.clear()

# --- INTERFACE ---
tab1, tab_cad, tab2, tab_ins, tab3, tab4 = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato & PDF"])

# --- TAB 1: ESTOQUE (Entradas e Lixeiras Mini) ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1.3, 2])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        # ADICIONADO KEY PARA EVITAR DUPLICIDADE
        m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"], key="sel_mod_estoque")
        t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_tam_estoque")
        col_q, col_v = st.columns(2)
        q_aq = col_q.number_input("Qtd", min_value=1, step=1, key="num_qtd_estoque")
        v_uni = col_v.number_input("R$ Unit. Compra", min_value=0.0, format="%.2f", key="num_val_estoque")
        if st.button("➕ Add Compra", key="btn_add_estoque"):
            st.session_state.carrinho_ent.append({"Modelo": m_aq, "Tamanho": t_aq, "Qtd": q_aq, "Unit": v_uni, "Sub": q_aq*v_uni})
            st.rerun()
        for i, item in enumerate(st.session_state.carrinho_ent):
            cl_del, cl_txt = st.columns([0.08, 0.92])
            if cl_del.button("🗑️", key=f"de_ent_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
            cl_txt.write(f"{item['Modelo']} ({item['Tamanho']}) x{item['Qtd']} - **R$ {item['Sub']:.2f}**")
        if st.session_state.carrinho_ent:
            total_c = sum(it['Sub'] for it in st.session_state.carrinho_ent)
            if st.button(f"✅ Confirmar R$ {total_c:.2f}", type="primary", key="btn_conf_estoque"):
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

# --- TAB CADASTRO MODELOS ---
with tab_cad:
    with st.form("f_cad_modelo"):
        n_m = st.text_input("Novo Nome de Modelo")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar Modelo"):
            if n_m:
                ni = {"Modelo": n_m}; ni.update(ipts)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.success("Cadastrado!"); st.rerun()

# --- TAB 2: VENDAS (Trava de Estoque + Pagamento) ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        # ADICIONADO KEY PARA EVITAR DUPLICIDADE
        v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique(), key="sel_cli_venda") if not df_clientes.empty else st.text_input("Cliente", key="ipt_cli_venda")
        v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="sel_mod_venda")
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_tam_venda")
        
        disp = 0
        if not df_estoque.empty and v_mod in df_estoque['Modelo'].values:
            disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            
        st.metric("Estoque Disponível", disp)
        v_qtd = st.number_input("Quantidade", min_value=0, max_value=disp, step=1, key="num_qtd_venda")
        v_pre = st.number_input("Preço Unitário R$", min_value=0.0, format="%.2f", key="num_val_venda")
        
        if st.button("➕ Adicionar ao Carrinho", key="btn_add_venda"):
            if v_qtd > 0:
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Preco": v_pre, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        st.subheader("📄 Itens do Pedido")
        for idx, it in enumerate(st.session_state.carrinho_v):
            cl_d, cl_t = st.columns([0.1, 0.9])
            if cl_d.button("🗑️", key=f"dv_item_{idx}"): st.session_state.carrinho_v.pop(idx); st.rerun()
            cl_t.write(f"{it['Mod']} ({it['Tam']}) x{it['Qtd']} - **R$ {it['Sub']:.2f}**")
            
        if st.session_state.carrinho_v:
            tot_v = sum(i['Sub'] for i in st.session_state.carrinho_v)
            st.markdown(f"--- \n ### Total do Pedido: R$ {tot_v:.2f}")
            st_pg = st.selectbox("Status de Pagamento", ["Pago", "Pendente"], key="sel_status_pg")
            fm_pg = st.selectbox("Forma de Recebimento", ["Pix", "Dinheiro", "Cartão", "Boleto"], key="sel_forma_pg")
            if st.button("🚀 Finalizar Pedido", type="primary", key="btn_finalizar_venda"):
                df_ev = df_estoque.copy()
                res_v = " | ".join([f"{it['Mod']}({it['Tam']}x{it['Qtd']})" for it in st.session_state.carrinho_v])
                for it in st.session_state.carrinho_v:
                    ix = df_ev.index[df_ev['Modelo'] == it['Mod']][0]
                    df_ev.at[ix, it['Tam']] = int(float(df_ev.at[ix, it['Tam']])) - it['Qtd']
                atualizar_planilha("Estoque", df_ev)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": res_v, "Valor Total": tot_v, "Status Pagto": st_pg, "Forma": fm_pg}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.success("Venda finalizada!"); st.rerun()

# --- TAB 3: INSUMOS (Com Lixeira Mini) ---
with tab_ins:
    st.subheader("🛠️ Gestão de Insumos")
    with st.form("f_insumo"):
        desc_i = st.text_input("O que comprou? (Sacolas, fios, etc)")
        val_i = st.number_input("Valor Pago R$", min_value=0.0, format="%.2f")
        if st.form_submit_button("Registrar Insumo"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])], ignore_index=True))
            st.success("Gasto registrado!"); st.rerun()
    
    st.markdown("---")
    for idx, row in df_insumos.iterrows():
        cl_del, cl_txt = st.columns([0.08, 0.92])
        if cl_del.button("🗑️", key=f"ex_ins_lista_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        cl_txt.write(f"{row['Data']} - {row['Descricao']} - **R$ {float(row['Valor']):.2f}**")

# --- TAB 4: CLIENTES (Loja/Cidade Separados) ---
with tab3:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cliente_novo"):
        c1, c2 = st.columns(2)
        n_c = c1.text_input("Nome Completo")
        l_c = c2.text_input("Nome da Loja")
        ci_c = c1.text_input("Cidade")
        t_c = c2.text_input("Telefone/WhatsApp")
        if st.form_submit_button("Cadastrar Cliente"):
            if n_c:
                atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": ci_c, "Telefone": t_c}])], ignore_index=True))
                st.success("Cliente cadastrado!"); st.rerun()
    st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB 5: EXTRATO & PDF DETALHADO ---
with tab4:
    st.subheader("🧾 Extrato Financeiro e PDF")
    u = pd.concat([
        df_pedidos.assign(Tipo="Venda"), 
        df_aquisicoes.assign(Tipo="Compra"), 
        df_insumos.assign(Tipo="Insumo").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    ], ignore_index=True)
    
    if not u.empty:
        u['Data_DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Filtro de visualização
        ver_tudo = st.checkbox("Ver histórico completo (fora do mês atual)")
        if not ver_tudo:
            f_df = u[(u['Data_DT'].dt.month == mes_atual) & (u['Data_DT'].dt.year == ano_atual)].sort_values('Data_DT', ascending=False)
        else:
            f_df = u.sort_values('Data_DT', ascending=False)
        
        st.dataframe(f_df[['Data', 'Tipo', 'Resumo', 'Valor Total', 'Status Pagto', 'Forma']], use_container_width=True, hide_index=True)
        
        vendas = pd.to_numeric(f_df[f_df['Tipo'] == "Venda"]['Valor Total']).sum()
        gastos = pd.to_numeric(f_df[f_df['Tipo'].isin(["Compra", "Insumo"])]['Valor Total']).sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Vendas (Receita)", f"R$ {vendas:.2f}")
        c2.metric("Saídas (Custos)", f"R$ {gastos:.2f}")
        c3.metric("Lucro Líquido", f"R$ {vendas - gastos:.2f}")

        if st.button("📄 Gerar PDF Detalhado"):
            pdf = PDF()
            pdf.add_page()
            
            pdf.chapter_title("RESUMO DO PERIODO")
            pdf.cell(0, 8, f"Total Vendas: R$ {vendas:.2f}", ln=True)
            pdf.cell(0, 8, f"Total Gastos: R$ {gastos:.2f}", ln=True)
            pdf.cell(0, 8, f"Saldo Final: R$ {vendas-gastos:.2f}", ln=True)
            pdf.ln(5)
            
            pdf.chapter_title("VENDAS DETALHADAS")
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 7, "Data", 1); pdf.cell(75, 7, "Cliente / Pedido", 1); pdf.cell(30, 7, "Valor", 1); pdf.cell(50, 7, "Pagto", 1, ln=True)
            pdf.set_font('Arial', '', 7)
            for _, r in f_df[f_df['Tipo'] == "Venda"].iterrows():
                pdf.cell(35, 6, str(r['Data']), 1)
                pdf.cell(75, 6, f"{str(r['Cliente'])[:15]} - {str(r['Resumo'])[:35]}", 1)
                pdf.cell(30, 6, f"R$ {float(r['Valor Total']):.2f}", 1)
                pdf.cell(50, 6, f"{r['Status Pagto']} ({r['Forma']})", 1, ln=True)
            
            st.download_button("📥 Clique para Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"relatorio_financeiro.pdf")
