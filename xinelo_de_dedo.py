import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Xinelo de Dedo v4.7", layout="wide", page_icon="🩴")

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

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def carregar_dados_v47():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is None or df.empty: return pd.DataFrame(columns=cols)
            df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = df.columns.str.strip()
            for c in cols:
                if c not in df.columns: df[c] = 0 if c in TAMANHOS_PADRAO else ""
            return df
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

d = carregar_dados_v47()
df_estoque, df_pedidos, df_clientes = d["est"], d["ped"], d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

def atualizar(aba, df):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("Salvo!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- BARRA LATERAL (REINSTITUÍDA) ---
with st.sidebar:
    st.header("💳 Painel Financeiro")
    if not df_pedidos.empty:
        # Fiado por Cliente
        pendentes = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pendentes.empty:
            total_pend = pendentes['Valor Total'].apply(limpar_valor).sum()
            st.warning(f"**Total a Receber: R$ {total_pend:.2f}**")
            res_cli = pendentes.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum())
            for cli, val in res_cli.items():
                st.caption(f"👤 {cli}: R$ {val:.2f}")
    
    st.divider()
    st.header("⚠️ Alertas de Estoque")
    if not df_estoque.empty:
        for _, r in df_estoque.iterrows():
            criticos = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
            if criticos:
                st.error(f"**{r['Modelo']}**\n{', '.join(criticos)}")

    st.divider()
    if st.button("🔄 Forçar Atualização Geral", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- INTERFACE ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 3. VENDAS (REINSTITUÍDO)
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛒 Registrar Pedido")
        v_cli = st.selectbox("Escolher Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Avulso"])
        v_mod = st.selectbox("Modelo para Venda", sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else [])
        v_tam = st.selectbox("Tamanho ", TAMANHOS_PADRAO)
        
        if v_mod:
            est_atual = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.info(f"Disponível: {est_atual} unidades")
            v_pre = st.number_input("Preço Unitário R$", min_value=0.0)
            v_qtd = st.number_input("Quantidade Venda", min_value=1, max_value=max(1, est_atual))
            
            if st.button("➕ Adicionar ao Carrinho"):
                if 'cart' not in st.session_state: st.session_state.cart = []
                st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
                st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            st.subheader("🛍️ Carrinho Atual")
            total_v, res_v = 0, []
            for i, it in enumerate(st.session_state.cart):
                sub = it['Pre'] * it['Qtd']
                st.write(f"**{it['Mod']} ({it['Tam']})** - {it['Qtd']}x R$ {it['Pre']:.2f} = R$ {sub:.2f}")
                if st.button("🗑️", key=f"del_v_{i}"): st.session_state.cart.pop(i); st.rerun()
                total_v += sub
                res_v.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            
            st.write(f"### Total: R$ {total_v:.2f}")
            v_stat = st.radio("Status do Pagamento", ["Pago", "Pendente"], horizontal=True)
            v_form = st.selectbox("Forma de Recebimento", ["Pix", "Dinheiro", "Cartão", "N/A"])
            
            if st.button("🚀 Finalizar Venda", type="primary"):
                # Baixa no estoque
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                atualizar("Estoque", df_e)
                # Registro no Pedido
                novo_p = {"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res_v), "Valor Total": total_v, "Status Pagto": v_stat, "Forma": v_form}
                atualizar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([novo_p])], ignore_index=True))
                st.session_state.cart = []; st.rerun()

# 6. EXTRATO (COM TODAS AS FUNÇÕES)
with tabs[5]:
    st.subheader("🧾 Histórico de Movimentações")
    p = df_pedidos.copy().assign(Tipo="VENDA", Ori="Pedidos")
    a = df_aquisicoes.copy().assign(Tipo="COMPRA", Ori="Aquisicoes")
    i = df_insumos.copy().assign(Tipo="INSUMO", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    uni = pd.concat([p, a, i], ignore_index=True)
    
    if not uni.empty:
        uni['DT_O'] = pd.to_datetime(uni['Data'], dayfirst=True, errors='coerce')
        for idx, r in uni.sort_values('DT_O', ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.05, 0.05, 0.1, 0.8])
                if c1.button("🗑️", key=f"ex_del_{idx}"):
                    origem = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                    atualizar(r['Ori'], origem[origem['Data'] != r['Data']])
                if r['Ori'] == "Pedidos" and "Pendente" in str(r.get('Status Pagto', '')):
                    if c2.button("✅", key=f"ex_pay_{idx}"):
                        df_p = df_pedidos.copy()
                        df_p.loc[df_p['Data'] == r['Data'], 'Status Pagto'] = "Pago"
                        atualizar("Pedidos", df_p)
                if r['Ori'] == "Pedidos":
                    c3.download_button("📄 PDF", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"ex_pdf_{idx}")
                
                txt_cli = f" | {r['Cliente']}" if pd.notna(r.get('Cliente')) and r['Cliente']!="" else ""
                st.write(f"**{r['Data']}** | {r['Tipo']}{txt_cli} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# 8. PREÇOS
with tabs[7]:
    st.subheader("📈 Evolução de Preços")
    if not df_hist_precos.empty:
        df_h = df_hist_precos.copy()
        df_h['DT'] = pd.to_datetime(df_h['Data'], dayfirst=True, errors='coerce')
        df_h['Preco_Unit'] = df_h['Preco_Unit'].apply(limpar_valor)
        sel = st.selectbox("Filtrar Modelo:", sorted(df_h['Modelo'].unique()))
        df_plot = df_h[df_h['Modelo'] == sel].sort_values('DT')
        if not df_plot.empty:
            st.line_chart(df_plot, x='DT', y='Preco_Unit')
            st.dataframe(df_plot[['Data', 'Preco_Unit']].sort_values('DT', ascending=False), hide_index=True)

# (Demais abas Estoque, Novo Modelo, Insumos, Clientes, Lembretes seguem a mesma lógica v4.6...)
