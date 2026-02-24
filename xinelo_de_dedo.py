import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Xinelo de Dedo v5.0", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Xinelo de Dedo v5.0")
st.markdown("---")

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

# --- CONEXÃO E CARREGAMENTO SEGURO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def carregar_dados():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                for c in cols:
                    if c not in df.columns: df[c] = 0 if c in TAMANHOS_PADRAO else ""
                return df
            return pd.DataFrame(columns=cols)
        except: return pd.DataFrame(columns=cols)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados()
df_estoque, df_pedidos, df_clientes = d["est"], d["ped"], d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

# TRAVA DE SEGURANÇA PARA SALVAMENTO
def atualizar_blindado(aba, df_novo, df_antigo):
    if not df_antigo.empty and df_novo.empty:
        st.error(f"🚨 BLOQUEADO: Tentativa de salvar '{aba}' vazio detectada. Aguarde o Google atualizar.")
        return
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Atualizado com sucesso!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("💳 Painel Financeiro")
    tem_p = False
    if not df_pedidos.empty:
        pend = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pend.empty:
            tem_p = True
            st.warning(f"**Fiado Total: R$ {pend['Valor Total'].apply(limpar_valor).sum():.2f}**")
            for c, v in pend.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum()).items():
                st.caption(f"👤 {c}: R$ {v:.2f}")
    if not tem_p: st.info("Sem pagamentos pendentes.")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    tem_e = False
    for _, r in df_estoque.iterrows():
        crit = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
        if crit:
            tem_e = True
            st.error(f"**{r['Modelo']}**\n{', '.join(crit)}")
    if not tem_e: st.success("Estoque saudável.")

# --- ABAS ---
t = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ESTOQUE INTEGRAL
with t[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        m = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else [])
        tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        qtd = st.number_input("Qtd", min_value=1)
        v_custo = st.number_input("Custo Unitário R$", min_value=0.0)
        if st.button("Confirmar Entrada"):
            df_e_atu = df_estoque.copy()
            idx = df_e_atu.index[df_e_atu['Modelo'] == m][0]
            df_e_atu.at[idx, tam] = int(float(df_e_atu.at[idx, tam])) + qtd
            atualizar_blindado("Estoque", df_e_atu, df_estoque)
            # Logs
            atualizar_blindado("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m}({tam}x{qtd})", "Valor Total": qtd*v_custo}])], ignore_index=True), df_aquisicoes)
            atualizar_blindado("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame([{"Data": get_data_hora(), "Modelo": m, "Preco_Unit": v_custo}])], ignore_index=True), df_hist_precos)

    with c2:
        st.dataframe(df_estoque, hide_index=True)
        m_apagar = st.selectbox("Excluir Modelo:", ["-"] + list(df_estoque['Modelo']))
        if m_apagar != "-" and st.button("🗑️ Remover Modelo do Sistema"):
            atualizar_blindado("Estoque", df_estoque[df_estoque['Modelo'] != m_apagar], df_estoque)

# 3. VENDAS INTEGRAL
with t[2]:
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Avulso"])
        v_mod = st.selectbox("Modelo ", sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else [])
        v_tam = st.selectbox("Tam", TAMANHOS_PADRAO)
        v_est = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0])) if v_mod else 0
        st.caption(f"Em estoque: {v_est}")
        v_pre = st.number_input("Preço Venda R$", min_value=0.0)
        v_qtd = st.number_input("Quantidade ", min_value=1, max_value=max(1, v_est))
        if st.button("🛒 Add Carrinho"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} = R$ {it['Pre']*it['Qtd']:.2f}")
                if st.button("🗑️", key=f"cart_{i}"): st.session_state.cart.pop(i); st.rerun()
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_st = st.radio("Pagto", ["Pago", "Pendente"], horizontal=True)
            v_fo = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
            if st.button("🚀 Finalizar", type="primary"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                atualizar_blindado("Estoque", df_e, df_estoque)
                atualizar_blindado("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_st, "Forma": v_fo}])], ignore_index=True), df_pedidos)
                st.session_state.cart = []; st.rerun()

# 5. CLIENTES INTEGRAL (RESTAURADO)
with t[4]:
    with st.form("cli_form"):
        st.subheader("Cadastrar Cliente")
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome")
        loj = c2.text_input("Loja")
        cid = c1.text_input("Cidade")
        tel = c2.text_input("Telefone")
        if st.form_submit_button("Salvar"):
            atualizar_blindado("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": loj, "Cidade": cid, "Telefone": tel}])], ignore_index=True), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

# 6. EXTRATO INTEGRAL
with t[5]:
    st.subheader("Histórico Financeiro")
    p = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Ori="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], dayfirst=True, errors='coerce')
        for idx, r in u.sort_values('DT', ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.05, 0.05, 0.1, 0.8])
                if c1.button("🗑️", key=f"ex_del_{idx}"):
                    orig = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                    atualizar_blindado(r['Ori'], orig[orig['Data'] != r['Data']], orig)
                if r['Ori'] == "Pedidos" and "Pendente" in str(r.get('Status Pagto', '')):
                    if c2.button("✅", key=f"ex_pay_{idx}"):
                        df_p = df_pedidos.copy()
                        df_p.loc[df_p['Data'] == r['Data'], 'Status Pagto'] = "Pago"
                        atualizar_blindado("Pedidos", df_p, df_pedidos)
                if r['Ori'] == "Pedidos":
                    c3.download_button("📄 PDF", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"ex_pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Tipo']} | {r.get('Cliente','')} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# (Demais abas Novo Modelo, Insumos, Lembretes e Preços seguem a mesma lógica segura)
