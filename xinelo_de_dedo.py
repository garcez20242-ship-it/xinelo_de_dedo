import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Xinelo de Dedo v5.1", layout="wide", page_icon="🩴")

# --- TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v5.1")
st.markdown("---")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES AUXILIARES ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

def gerar_recibo(dados_venda):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA - XINELO DE DEDO", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data/Hora: {dados_venda.get('Data', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda.get('Cliente', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda.get('Status Pagto', 'N/A')}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        resumo = str(dados_venda.get('Resumo', '')).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CARREGAMENTO TEIMOSO (ANTI-ERRO 429) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_dados_completos():
    def ler_aba(aba, colunas_alvo):
        for tentativa in range(3):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
                if df is not None and not df.empty and len(df.columns) >= 1:
                    df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                    df.columns = df.columns.str.strip()
                    return df
                time.sleep(1.5)
            except:
                time.sleep(1.5)
        return pd.DataFrame(columns=colunas_alvo)

    return {
        "est": ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler_aba("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler_aba("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler_aba("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

# Carregar Dados
dados = carregar_dados_completos()
df_estoque, df_pedidos, df_clientes = dados["est"], dados["ped"], dados["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = dados["ins"], dados["lem"], dados["his"], dados["aqui"]

# --- FUNÇÃO DE SALVAMENTO COM TRAVA DE SEGURANÇA BRUTA ---
def salvar_com_seguranca(aba, df_novo, df_antigo):
    # Se o antigo tinha dados e o novo está vindo vazio, o Google falhou. NÃO SALVA.
    if not df_antigo.empty and df_novo.empty:
        st.error(f"🚨 ERRO: A aba {aba} tentou zerar os dados. Operação interrompida para segurança.")
        return

    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Sincronizado com o Google!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}. Aguarde 30s.")

# --- BARRA LATERAL (ORDEM SOLICITADA) ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("💳 Painel Financeiro")
    if not df_pedidos.empty:
        pendentes = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pendentes.empty:
            total_fiado = pendentes['Valor Total'].apply(limpar_valor).sum()
            st.warning(f"**Fiado Total: R$ {total_fiado:.2f}**")
            resumo_cli = pendentes.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum())
            for cli, val in resumo_cli.items():
                st.caption(f"👤 {cli}: R$ {val:.2f}")
        else: st.info("Nenhum pagamento pendente.")
    else: st.info("Sem dados de vendas.")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    tem_alerta = False
    if not df_estoque.empty:
        for _, row in df_estoque.iterrows():
            baixos = [f"{t}({int(float(row[t]))})" for t in TAMANHOS_PADRAO if (int(float(row[t])) if row[t] != "" else 0) <= 3]
            if baixos:
                st.error(f"**{row['Modelo']}**\n{', '.join(baixos)}")
                tem_alerta = True
    if not tem_alerta: st.success("Estoque OK.")

# --- INTERFACE PRINCIPAL ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ABA ESTOQUE
with tabs[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada")
        if not df_estoque.empty:
            m_ent = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()))
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            q_ent = st.number_input("Quantidade", min_value=1)
            c_ent = st.number_input("Custo Unitário R$", min_value=0.0)
            if st.button("Confirmar Entrada"):
                df_atu = df_estoque.copy()
                idx = df_atu.index[df_atu['Modelo'] == m_ent][0]
                df_atu.at[idx, t_ent] = int(float(df_atu.at[idx, t_ent])) + q_ent
                salvar_com_seguranca("Estoque", df_atu, df_estoque)
                # Histórico e Aquisições
                salvar_com_seguranca("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m_ent}({t_ent}x{q_ent})", "Valor Total": q_ent*c_ent}])], ignore_index=True), df_aquisicoes)
                salvar_com_seguranca("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame([{"Data": get_data_hora(), "Modelo": m_ent, "Preco_Unit": c_ent}])], ignore_index=True), df_hist_precos)
    with c2:
        st.subheader("📋 Inventário")
        st.dataframe(df_estoque, hide_index=True)

# 2. NOVO MODELO
with tabs[1]:
    with st.form("novo_mod"):
        st.subheader("✨ Cadastrar Novo Modelo")
        nome_m = st.text_input("Nome do Modelo")
        if st.form_submit_button("Criar"):
            if nome_m:
                novo_m = {"Modelo": nome_m}; novo_m.update({t: 0 for t in TAMANHOS_PADRAO})
                salvar_com_seguranca("Estoque", pd.concat([df_estoque, pd.DataFrame([novo_m])], ignore_index=True), df_estoque)

# 3. VENDAS
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛒 Pedido")
        v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Avulso"])
        v_mod = st.selectbox("Modelo ", sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else [])
        v_tam = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço R$", min_value=0.0)
        v_qtd = st.number_input("Qtd ", min_value=1)
        if st.button("Adicionar Item"):
            if 'carrinho' not in st.session_state: st.session_state.carrinho = []
            st.session_state.carrinho.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c2:
        if 'carrinho' in st.session_state and st.session_state.carrinho:
            st.subheader("🛍️ Carrinho")
            t_venda, r_venda = 0, []
            for i, item in enumerate(st.session_state.carrinho):
                sub = item['Pre'] * item['Qtd']
                st.write(f"{item['Mod']} ({item['Tam']}) x{item['Qtd']} = R$ {sub:.2f}")
                t_venda += sub; r_venda.append(f"{item['Mod']}({item['Tam']}x{item['Qtd']})")
            v_st = st.radio("Pagamento", ["Pago", "Pendente"], horizontal=True)
            v_fo = st.selectbox("Meio", ["Pix", "Dinheiro", "Cartão"])
            if st.button("Finalizar Venda", type="primary"):
                df_e = df_estoque.copy()
                for item in st.session_state.carrinho:
                    idx = df_e.index[df_e['Modelo'] == item['Mod']][0]
                    df_e.at[idx, item['Tam']] = int(float(df_e.at[idx, item['Tam']])) - item['Qtd']
                salvar_com_seguranca("Estoque", df_e, df_estoque)
                salvar_com_seguranca("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(r_venda), "Valor Total": t_venda, "Status Pagto": v_st, "Forma": v_fo}])], ignore_index=True), df_pedidos)
                st.session_state.carrinho = []; st.rerun()

# 4. INSUMOS
with tabs[3]:
    with st.form("insumo"):
        desc_i = st.text_input("Gasto com quê?"); val_i = st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Salvar Gasto"):
            salvar_com_seguranca("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])], ignore_index=True), df_insumos)

# 5. CLIENTES (COMPLETO)
with tabs[4]:
    with st.form("f_cli"):
        st.subheader("👥 Cadastro Completo")
        col1, col2 = st.columns(2)
        n_c = col1.text_input("Nome")
        l_c = col2.text_input("Loja")
        c_c = col1.text_input("Cidade")
        t_c = col2.text_input("Telefone (WhatsApp)")
        if st.form_submit_button("Cadastrar Cliente"):
            salvar_com_seguranca("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n_c, "Loja": l_c, "Cidade": c_c, "Telefone": t_c}])], ignore_index=True), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

# 6. EXTRATO (COMPLETO COM LIXEIRA E PDF)
with tabs[5]:
    st.subheader("🧾 Movimentações")
    vendas = df_pedidos.assign(Tipo="VENDA", Ori="Pedidos")
    compras = df_aquisicoes.assign(Tipo="COMPRA", Ori="Aquisicoes")
    insumos = df_insumos.assign(Tipo="INSUMO", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    tudo = pd.concat([vendas, compras, insumos], ignore_index=True)
    if not tudo.empty:
        tudo['DT_ORDEM'] = pd.to_datetime(tudo['Data'], dayfirst=True, errors='coerce')
        for idx, row in tudo.sort_values('DT_ORDEM', ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.05, 0.05, 0.1, 0.8])
                if c1.button("🗑️", key=f"del_{idx}"):
                    df_origem = df_pedidos if row['Ori'] == "Pedidos" else df_aquisicoes if row['Ori'] == "Aquisicoes" else df_insumos
                    salvar_com_seguranca(row['Ori'], df_origem[df_origem['Data'] != row['Data']], df_origem)
                if row['Ori'] == "Pedidos" and "Pendente" in str(row['Status Pagto']):
                    if c2.button("✅", key=f"pay_{idx}"):
                        df_p = df_pedidos.copy()
                        df_p.loc[df_p['Data'] == row['Data'], 'Status Pagto'] = "Pago"
                        salvar_com_seguranca("Pedidos", df_p, df_pedidos)
                if row['Ori'] == "Pedidos":
                    c3.download_button("📄 PDF", gerar_recibo(row), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{row['Data']}** | {row['Tipo']} | {row.get('Cliente', '')} | {row['Resumo']} | **R$ {limpar_valor(row['Valor Total']):.2f}**")

# 7. LEMBRETES
with tabs[6]:
    with st.form("lembrete"):
        txt_l = st.text_input("O que pagar?"); data_l = st.date_input("Vencimento"); val_l = st.number_input("Valor R$ ", min_value=0.0)
        if st.form_submit_button("Agendar"):
            salvar_com_seguranca("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": txt_l, "Data": data_l.strftime("%d/%m/%Y"), "Valor": val_l}])], ignore_index=True), df_lembretes)
    for i, r in df_lembretes.iterrows():
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# 8. PREÇOS (GRÁFICO)
with tabs[7]:
    if not df_hist_precos.empty:
        df_h = df_hist_precos.copy()
        df_h['DT'] = pd.to_datetime(df_h['Data'], dayfirst=True, errors='coerce')
        df_h['Preco_Unit'] = df_h['Preco_Unit'].apply(limpar_valor)
        sel_m = st.selectbox("Ver evolução de:", sorted(df_h['Modelo'].unique()))
        df_filtrado = df_h[df_h['Modelo'] == sel_m].sort_values('DT')
        st.line_chart(df_filtrado, x='DT', y='Preco_Unit')
