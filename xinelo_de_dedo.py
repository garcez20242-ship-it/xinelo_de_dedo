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
    st.header("💳 Alertas Financeiros")
    hoje = datetime.now().date()
    tem_pag = False
    if not df_lembretes.empty:
        df_l_temp = df_lembretes.copy()
        df_l_temp['Data_DT'] = pd.to_datetime(df_l_temp['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l_temp[df_l_temp['Data_DT'] <= hoje]
        for _, r in pends.iterrows():
            st.error(f"**CONTA:** {r['Nome']} ({r['Data']})")
            tem_pag = True
    if not tem_pag: st.success("✅ Tudo em dia")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    if df_estoque.empty:
        st.info("Nenhum modelo cadastrado para monitorar.")
    else:
        alerta_vazio = True
        for _, row in df_estoque.iterrows():
            criticos = [f"{t}({int(float(row[t])) if row[t] != '' else 0}un)" for t in TAMANHOS_PADRAO if (int(float(row[t])) if row[t] != '' else 0) <= 3]
            if criticos:
                st.warning(f"**{row['Modelo']}**\n{', '.join(criticos)}")
                alerta_vazio = False
        if alerta_vazio: st.success("✅ Estoque abastecido")

# --- INTERFACE ---
st.title("🩴 Gestão Xinelo de Dedo v3.1")
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços Compra"
])

# --- TAB 1: ESTOQUE (ENTRADA MÚLTIPLA) ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        modelos_disponiveis = df_estoque['Modelo'].unique() if not df_estoque.empty else []
        
        if len(modelos_disponiveis) == 0:
            st.warning("Cadastre um modelo primeiro na aba 'Novo Modelo'!")
        else:
            m_ent = st.selectbox("Modelo", modelos_disponiveis)
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            q_ent = st.number_input("Quantidade", min_value=1)
            v_ent = st.number_input("Custo Unitário R$", min_value=0.0)
            if st.button("➕ Adicionar à Lista"):
                st.session_state.carrinho_ent.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Unit": v_ent, "Sub": q_ent*v_ent})
                st.rerun()
        
        for i, it in enumerate(st.session_state.carrinho_ent):
            col_l, col_r = st.columns([0.8, 0.2])
            col_l.write(f"• {it['Modelo']} {it['Tam']} (x{it['Qtd']}) - R${it['Unit']:.2f}un")
            if col_r.button("🗑️", key=f"del_e_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()

        if st.session_state.carrinho_ent:
            if st.button("✅ Confirmar Entrada de Tudo", type="primary"):
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
        if df_estoque.empty:
            st.info("Nenhum modelo em estoque. Use a aba ao lado para cadastrar.")
        else:
            for idx, r in df_estoque.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"d_inv_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                ct.write(f"**{r['Modelo']}**")
            st.dataframe(df_estoque.style.applymap(colorir_estoque, subset=TAMANHOS_PADRAO), hide_index=True)

# --- TAB NOVO MODELO (CADASTRO) ---
with tab_cad:
    st.subheader("✨ Cadastrar Novo Modelo de Chinelo")
    with st.form("novo_mod"):
        nm = st.text_input("Nome do Modelo (Ex: Havaiana Branca)")
        cols = st.columns(5)
        vals = {t: cols[i%5].number_input(f"Qtd Inicial {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar no Sistema"):
            if nm.strip() == "": st.error("O nome do modelo é obrigatório!")
            else:
                d_novo = {"Modelo": nm}; d_novo.update(vals)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([d_novo])], ignore_index=True)); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Carrinho de Venda")
        if df_estoque.empty:
            st.warning("Não há produtos no estoque para vender!")
        else:
            v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["Cliente Avulso"])
            v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique())
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            
            # Verificar estoque disponível
            estoque_atual = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.write(f"Estoque disponível: **{estoque_atual}**")
            
            v_pre = st.number_input("Preço de Venda Unit. R$", min_value=0.0)
            v_qtd = st.number_input("Qtd Venda", min_value=1, max_value=max(1, estoque_atual))
            
            if st.button("➕ Adicionar Item"):
                if estoque_atual >= v_qtd:
                    st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                    st.rerun()
                else: st.error("Quantidade acima do estoque!")
    with c2:
        for i, it in enumerate(st.session_state.carrinho_v):
            col_l, col_r = st.columns([0.8, 0.2])
            col_l.write(f"{it['Mod']} {it['Tam']} (x{it['Qtd']}) - R$ {it['Sub']:.2f}")
            if col_r.button("🗑️", key=f"dv_{i}"): st.session_state.carrinho_v.pop(i); st.rerun()
        
        if st.session_state.carrinho_v:
            total_v = sum(x['Sub'] for x in st.session_state.carrinho_v)
            st.write(f"### Total Venda: R$ {total_v:.2f}")
            if st.button("Finalizar Venda", type="primary"):
                df_e_v = df_estoque.copy()
                for x in st.session_state.carrinho_v:
                    ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                    df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                resumo_venda = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.carrinho_v])
                atualizar_planilha("Estoque", df_e_v)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": resumo_venda, "Valor Total": total_v, "Status Pagto": "Pago", "Forma": "Pix"}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    with st.form("ins_f"):
        d_i = st.text_input("Descrição do Gasto (Ex: Embalagens, Frete)")
        v_i = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True)); st.rerun()
    st.write("---")
    if df_insumos.empty: st.info("Nenhum insumo registrado.")
    else:
        for idx, r in df_insumos.iterrows():
            cd, ct = st.columns([0.1, 0.9])
            if cd.button("🗑️", key=f"d_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
            ct.write(f"{r['Data']} - {r['Descricao']} - **R$ {limpar_valor(r['Valor']):.2f}**")

# --- TAB CLIENTES ---
with tab3:
    with st.form("cli_f"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome Cliente")
        l = c2.text_input("Loja")
        cid = c1.text_input("Cidade")
        tel = c2.text_input("Telefone")
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True)); st.rerun()
    
    if df_clientes.empty: st.info("Nenhum cliente cadastrado.")
    else:
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)
        for idx, r in df_clientes.iterrows():
            if st.button(f"Remover {r['Nome']}", key=f"d_cli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()

# --- TAB EXTRATO ---
with tab4:
    st.subheader("🧾 Histórico Financeiro")
    f_30 = st.checkbox("Filtrar últimos 30 dias", value=True)
    p = df_pedidos.assign(Tipo="Venda", Origem="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Origem="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Origem="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    
    if u.empty: st.info("ℹ️ Nenhuma movimentação registrada no sistema.")
    else:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        if f_30: u = u[u['DT'] >= (datetime.now() - timedelta(days=30))]
        u = u.sort_values('DT', ascending=False)
        for idx, r in u.iterrows():
            c_d, c_t = st.columns([0.1, 0.9])
            if c_d.button("🗑️", key=f"d_ext_{idx}"):
                if r['Origem'] == "Pedidos": atualizar_planilha("Pedidos", df_pedidos[df_pedidos['Data'] != r['Data']])
                elif r['Origem'] == "Aquisicoes": atualizar_planilha("Aquisicoes", df_aquisicoes[df_aquisicoes['Data'] != r['Data']])
                elif r['Origem'] == "Insumos": atualizar_planilha("Insumos", df_insumos[df_insumos['Data'] != r['Data']])
                st.rerun()
            c_t.write(f"**{r['Data']}** | {r['Tipo']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# --- TAB LEMBRETES ---
with tab5:
    with st.form("lem_f"):
        ln = st.text_input("Título da Conta/Lembrete")
        ld = st.date_input("Data Vencimento")
        lv = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Agendar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    if df_lembretes.empty: st.info("Sem lembretes.")
    else:
        for idx, r in df_lembretes.iterrows():
            if st.button("🗑️", key=f"d_lem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
            st.write(f"📅 {r['Data']} - **{r['Nome']}** - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB HISTÓRICO PREÇOS ---
with tab6:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        modelos_h = df_hist_precos['Modelo'].unique()
        sel = st.selectbox("Selecione o Modelo para ver evolução de preço", modelos_h)
        df_plot = df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT')
        st.line_chart(df_plot, x='DT', y='Preco_Unit')
        st.write("### Histórico Geral")
        st.dataframe(df_hist_precos.sort_values('DT', ascending=False), hide_index=True)
    else: st.info("O histórico será populado conforme você registrar novas 'Entradas de Mercadoria'.")
