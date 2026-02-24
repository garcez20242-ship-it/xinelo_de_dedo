import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io

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

def gerar_recibo(dados_venda):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "RECIBO DE VENDA - XINELO DE DEDO", ln=True, align="C")
    pdf.ln(5)
    
    # Informações Gerais
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 8, f"Data/Hora: {dados_venda['Data']}", ln=True)
    pdf.cell(190, 8, f"Cliente: {dados_venda['Cliente']}", ln=True)
    pdf.cell(190, 8, f"Status: {dados_venda['Status Pagto']}", ln=True)
    pdf.ln(5)
    
    # Itens
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, "Itens do Pedido:", ln=True)
    pdf.set_font("Arial", "", 11)
    resumo_limpo = dados_venda['Resumo'].replace(" | ", "\n")
    pdf.multi_cell(190, 8, resumo_limpo)
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda['Valor Total']):.2f}", ln=True, align="R")
    
    # Rodapé
    pdf.set_font("Arial", "I", 8)
    pdf.ln(10)
    pdf.cell(190, 5, "Obrigado pela preferência!", ln=True, align="C")
    
    return pdf.output(dest='S').encode('latin-1')

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
               ler_aba("Lembretes", ["Nome", "Data", "Valor"]), \
               ler_aba("Historico_Precos", ["Data", "Modelo", "Preco_Unit"])
    except: return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos, df_lembretes, df_hist_precos = carregar_dados()

def atualizar_planilha(aba, dataframe):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
    st.cache_data.clear()

# --- ESTILIZAÇÃO ---
def colorir_estoque(val):
    try:
        v = int(float(val))
        if v == 0: return 'background-color: #ff4b4b; color: white'
        if v <= 3: return 'background-color: #ffeb3b; color: black'
        return ''
    except: return ''

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("💳 Gestão Financeira")
    hoje = datetime.now().date()
    tem_pag = False
    if not df_lembretes.empty:
        df_l_temp = df_lembretes.copy()
        df_l_temp['Data_DT'] = pd.to_datetime(df_l_temp['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l_temp[df_l_temp['Data_DT'] <= hoje]
        if not pends.empty:
            st.subheader("🚩 Contas a Pagar")
            for _, r in pends.iterrows():
                st.error(f"**{r['Nome']}**: R$ {limpar_valor(r['Valor']):.2f}")
                tem_pag = True
    if not tem_pag: st.success("✅ Sem contas vencidas")

    st.divider()
    st.subheader("💰 Contas a Receber")
    if not df_pedidos.empty:
        df_vendas_pendentes = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not df_vendas_pendentes.empty:
            df_vendas_pendentes['Valor_Num'] = df_vendas_pendentes['Valor Total'].apply(limpar_valor)
            resumo_divida = df_vendas_pendentes.groupby('Cliente')['Valor_Num'].sum()
            for cli, valor in resumo_divida.items():
                st.warning(f"**{cli}**: R$ {valor:.2f}")
        else: st.info("Não há vendas pendentes.")
    else: st.info("Sem histórico de vendas.")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    if df_estoque.empty: st.info("Nenhum modelo cadastrado.")
    else:
        alerta_vazio = True
        for _, row in df_estoque.iterrows():
            criticos = [f"{t}({int(float(row[t])) if row[t] != '' else 0}un)" for t in TAMANHOS_PADRAO if (int(float(row[t])) if row[t] != '' else 0) <= 3]
            if criticos:
                st.warning(f"**{row['Modelo']}**\n{', '.join(criticos)}")
                alerta_vazio = False
        if alerta_vazio: st.success("✅ Estoque abastecido")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Gestão Xinelo de Dedo v3.5")
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços Compra"])
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5, tab6 = tabs

# --- TAB 1: ESTOQUE ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        modelos_dis = df_estoque['Modelo'].unique() if not df_estoque.empty else []
        if len(modelos_dis) == 0: st.warning("Cadastre um modelo primeiro!")
        else:
            m_ent = st.selectbox("Modelo", modelos_dis, key="sel_mod_estoque")
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_tam_estoque")
            q_ent = st.number_input("Quantidade", min_value=1, key="num_qtd_estoque")
            v_ent = st.number_input("Custo Unitário R$", min_value=0.0, key="num_val_estoque")
            if st.button("➕ Adicionar à Entrada"):
                st.session_state.carrinho_ent.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Unit": v_ent, "Sub": q_ent*v_ent})
                st.rerun()
        for i, it in enumerate(st.session_state.carrinho_ent):
            cl, cr = st.columns([0.8, 0.2])
            cl.write(f"• {it['Modelo']} {it['Tam']} (x{it['Qtd']})")
            if cr.button("🗑️", key=f"del_e_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
        if st.session_state.carrinho_ent:
            if st.button("✅ Confirmar Entrada", type="primary", key="btn_conf_estoque"):
                df_e_atu = df_estoque.copy()
                hist_novos, res_txt, total_geral = [], [], 0
                for it in st.session_state.carrinho_ent:
                    idx = df_e_atu.index[df_e_atu['Modelo'] == it['Modelo']][0]
                    df_e_atu.at[idx, it['Tam']] = int(float(df_e_atu.at[idx, it['Tam']])) + it['Qtd']
                    hist_novos.append({"Data": get_data_hora(), "Modelo": it['Modelo'], "Preco_Unit": it['Unit']})
                    res_txt.append(f"{it['Modelo']}({it['Tam']}x{it['Qtd']})")
                    total_geral += it['Sub']
                atualizar_planilha("Estoque", df_e_atu)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_txt), "Valor Total": total_geral}])], ignore_index=True))
                atualizar_planilha("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(hist_novos)], ignore_index=True))
                st.session_state.carrinho_ent = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        if df_estoque.empty: st.info("Estoque vazio.")
        else:
            for idx, r in df_estoque.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"d_inv_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                ct.write(f"**{r['Modelo']}**")
            st.dataframe(df_estoque.style.applymap(colorir_estoque, subset=TAMANHOS_PADRAO), hide_index=True)

# --- TAB NOVO MODELO ---
with tab_cad:
    with st.form("novo_mod"):
        st.subheader("✨ Cadastrar Novo Modelo")
        nm = st.text_input("Nome do Modelo")
        cols = st.columns(5)
        vals = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if nm:
                d_novo = {"Modelo": nm}; d_novo.update(vals)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([d_novo])], ignore_index=True)); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        if df_estoque.empty: st.warning("Sem estoque.")
        else:
            v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["Cliente Avulso"], key="sel_cli_venda")
            v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique(), key="sel_mod_venda")
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_tam_venda")
            est_disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.write(f"Disponível: {est_disp}")
            v_pre = st.number_input("Preço Venda R$", min_value=0.0, key="num_val_venda")
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, est_disp), key="num_qtd_venda")
            if st.button("➕ Adicionar Item", key="btn_add_venda"):
                if est_disp >= v_qtd:
                    st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                    st.rerun()
    with c2:
        st.subheader("📄 Resumo da Venda")
        for i, it in enumerate(st.session_state.carrinho_v):
            st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']} - R$ {it['Sub']:.2f}")
        if st.session_state.carrinho_v:
            total_v = sum(x['Sub'] for x in st.session_state.carrinho_v)
            st.write(f"### Total: R$ {total_v:.2f}")
            status_v = st.radio("Status do Pagamento", ["Pago", "Pendente"], horizontal=True, key="rad_status_venda")
            forma_v = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "N/A"], key="sel_forma_venda")
            if st.button("Finalizar Venda", type="primary", key="btn_conf_venda"):
                df_e_v = df_estoque.copy()
                for x in st.session_state.carrinho_v:
                    ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                    df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                resumo = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.carrinho_v])
                atualizar_planilha("Estoque", df_e_v)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": resumo, "Valor Total": total_v, "Status Pagto": status_v, "Forma": forma_v}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    with st.form("ins_f"):
        st.subheader("🛠️ Registrar Gasto")
        d_i = st.text_input("Descrição"); v_i = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar Insumo"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True)); st.rerun()
    for idx, r in df_insumos.iterrows():
        cl, cr = st.columns([0.1, 0.9])
        if cl.button("🗑️", key=f"d_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        cr.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB CLIENTES ---
with tab3:
    with st.form("cli_f"):
        st.subheader("👥 Cadastro de Clientes")
        c1, c2 = st.columns(2); n = c1.text_input("Nome"); l = c2.text_input("Loja")
        cid = c1.text_input("Cidade"); tel = c2.text_input("Telefone")
        if st.form_submit_button("Cadastrar Cliente"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True)); st.rerun()
    st.dataframe(df_clientes, use_container_width=True, hide_index=True)
    for idx, r in df_clientes.iterrows():
        if st.button(f"Remover {r['Nome']}", key=f"d_cli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()

# --- TAB EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato Financeiro")
    f_30 = st.checkbox("Últimos 30 dias", value=True, key="chk_30_extrato")
    p = df_pedidos.assign(Tipo="Venda", Origem="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Origem="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Origem="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        if f_30: u = u[u['DT'] >= (datetime.now() - timedelta(days=30))]
        u = u.sort_values('DT', ascending=False)
        for idx, r in u.iterrows():
            c_d, c_b, c_pdf, c_t = st.columns([0.05, 0.12, 0.08, 0.75])
            if c_d.button("🗑️", key=f"d_ext_{idx}"):
                if r['Origem'] == "Pedidos": atualizar_planilha("Pedidos", df_pedidos[df_pedidos['Data'] != r['Data']])
                elif r['Origem'] == "Aquisicoes": atualizar_planilha("Aquisicoes", df_aquisicoes[df_aquisicoes['Data'] != r['Data']])
                elif r['Origem'] == "Insumos": atualizar_planilha("Insumos", df_insumos[df_insumos['Data'] != r['Data']])
                st.rerun()
            if r['Origem'] == "Pedidos" and r['Status Pagto'] == "Pendente":
                if c_b.button("✅ Receber", key=f"bx_{idx}"):
                    df_p_atu = df_pedidos.copy()
                    mask = (df_p_atu['Data'] == r['Data']) & (df_p_atu['Cliente'] == r['Cliente'])
                    df_p_atu.loc[mask, 'Status Pagto'] = "Pago"
                    atualizar_planilha("Pedidos", df_p_atu); st.rerun()
            if r['Origem'] == "Pedidos":
                pdf_bytes = gerar_recibo(r)
                c_pdf.download_button(label="📄 PDF", data=pdf_bytes, file_name=f"recibo_{idx}.pdf", mime="application/pdf", key=f"pdf_down_{idx}")
            status_p = r['Status Pagto'] if r['Origem'] == "Pedidos" else "Pago"
            prefixo = "🔴 [PENDENTE]" if (r['Origem'] == "Pedidos" and status_p == "Pendente") else "🟢" if r['Tipo'] == "Venda" else "⚪"
            cliente_str = f" | {r['Cliente']}" if r['Tipo'] == "Venda" else ""
            c_t.write(f"{prefixo} **{r['Data']}** | {r['Tipo']}{cliente_str} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")
    else: st.info("Nenhuma movimentação.")

# --- TAB LEMBRETES ---
with tab5:
    with st.form("lem_f"):
        st.subheader("📅 Agendar Pagamento"); ln = st.text_input("Título"); ld = st.date_input("Vencimento"); lv = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"d_lem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB HISTÓRICO PREÇOS ---
with tab6:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        sel = st.selectbox("Evolução de Preço:", df_hist_precos['Modelo'].unique(), key="sel_hist_preco")
        st.line_chart(df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT'), x='DT', y='Preco_Unit')
        st.dataframe(df_hist_precos.sort_values('DT', ascending=False), hide_index=True)
    else: st.info("Sem dados de histórico.")
