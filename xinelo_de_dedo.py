import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Master v7.8", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Master v7.8 - Estabilidade Total")

# --- CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES DE UTILIDADE ---
def get_data_hora():
    """Retorna a data e hora atual no fuso horário correto"""
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    """Converte valores de moeda ou texto sujo para float"""
    try:
        if pd.isna(valor) or str(valor).strip() == "": 
            return 0.0
        return float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except:
        return 0.0

def gerar_recibo(r):
    """Gera um PDF básico para registro"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "DOCUMENTO DE REGISTRO", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.ln(10)
        pdf.cell(190, 10, f"Data: {r.get('Data', '')}", ln=True)
        pdf.cell(190, 10, f"Envolvido: {r.get('Cliente', 'N/A')}", ln=True)
        pdf.multi_cell(190, 8, f"Resumo: {r.get('Resumo', '')}")
        pdf.cell(190, 10, f"Total: R$ {limpar_valor(r.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        return b""

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2)
def carregar_dados():
    """Carrega todas as abas garantindo a existência de colunas essenciais"""
    abas_necessarias = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor"]
    }
    leitura = {}
    for aba, colunas in abas_necessarias.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None:
                # Limpa colunas vazias/fantasmas e espaços nos nomes
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = [str(c).strip() for c in df.columns]
                
                # Validação: Se a coluna principal não existe, reconstrói o dataframe
                if aba == "Estoque" and "Modelo" not in df.columns:
                    df = pd.DataFrame(columns=colunas)
                elif aba != "Estoque" and df.empty:
                    df = pd.DataFrame(columns=colunas)
                
                # Ordenação Alfabética para Estoque e Clientes
                if aba == "Estoque" and not df.empty:
                    df = df.sort_values(by="Modelo")
                elif aba == "Clientes" and not df.empty:
                    df = df.sort_values(by="Nome")
                    
                leitura[aba] = df
            else:
                leitura[aba] = pd.DataFrame(columns=colunas)
        except Exception:
            leitura[aba] = pd.DataFrame(columns=colunas)
    return leitura

def salvar_seguro(aba, df_novo):
    """Executa a atualização no Google Sheets com limpeza de cache"""
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        time.sleep(1) # Delay técnico para propagação do Google
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na aba {aba}: {e}")
        return False

# Carregamento inicial
dados = carregar_dados()
df_est = dados["Estoque"]
df_ped = dados["Pedidos"]
df_cli = dados["Clientes"]
df_ins = dados["Insumos"]
df_lem = dados["Lembretes"]

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Sincronizar Agora"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.subheader("🔔 Contas Próximas")
    if not df_lem.empty:
        for _, row in df_lem.iterrows():
            if row['Nome']:
                st.warning(f"**{row['Nome']}**\nVence: {row['Vencimento']}\nR$ {row['Valor']}")

# --- SISTEMA DE ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novos Modelos", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

# --- ABA 1: ESTOQUE ---
with tabs[0]:
    st.subheader("📋 Gestão de Inventário")
    
    # Campo de Pesquisa Rápida
    pesquisa = st.text_input("🔍 Pesquisar por nome do modelo...", "", key="search_main").strip().lower()
    
    if not df_est.empty and "Modelo" in df_est.columns:
        df_mostrar = df_est[df_est['Modelo'].str.lower().str.contains(pesquisa)] if pesquisa else df_est
        st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
        
        # Minimizado: Entrada de Compra
        with st.expander("➕ Entrada de Compra (Lote Multi-Modelo)"):
            if 'lote_compra' not in st.session_state: st.session_state.lote_compra = []
            
            c1, c2, c3 = st.columns(3)
            mod_sel = c1.selectbox("Selecione o Modelo", sorted(df_est['Modelo'].unique()), key="ent_mod")
            tam_sel = c2.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            qtd_sel = c3.number_input("Quantidade", min_value=1, value=1, key="ent_qtd")
            
            if st.button("Adicionar ao Lote"):
                st.session_state.lote_compra.append({"Modelo": mod_sel, "Tam": tam_sel, "Qtd": qtd_sel})
                st.rerun()
            
            if st.session_state.lote_compra:
                st.table(pd.DataFrame(st.session_state.lote_compra))
                c_val, c_btn = st.columns([2, 1])
                valor_entrada = c_val.number_input("Valor Total da NF/Compra (R$)", min_value=0.0)
                
                if c_btn.button("🏁 Finalizar Entrada", type="primary"):
                    with st.spinner("Processando estoque..."):
                        df_temp = df_est.copy()
                        resumo_items = []
                        for item in st.session_state.lote_compra:
                            idx = df_temp.index[df_temp['Modelo'] == item['Modelo']][0]
                            # Converte valor atual para inteiro com segurança
                            val_orig = df_temp.at[idx, item['Tam']]
                            atual = int(float(val_orig)) if val_orig != "" and not pd.isna(val_orig) else 0
                            df_temp.at[idx, item['Tam']] = atual + item['Qtd']
                            resumo_items.append(f"{item['Modelo']}({item['Tam']}x{item['Qtd']})")
                        
                        if salvar_seguro("Estoque", df_temp):
                            # Registra no extrato
                            nova_linha_ped = pd.DataFrame([{
                                "Data": get_data_hora(),
                                "Cliente": "FORNECEDOR",
                                "Resumo": f"ENTRADA: {' | '.join(resumo_items)}",
                                "Valor Total": valor_entrada,
                                "Status Pagto": "Pago"
                            }])
                            salvar_seguro("Pedidos", pd.concat([df_ped, nova_linha_ped], ignore_index=True))
                            st.session_state.lote_compra = []
                            st.success("Estoque atualizado com sucesso!")
                            time.sleep(1)
                            st.rerun()

        # Minimizado: Apagar Modelo
        with st.expander("🗑️ Remover Modelo do Sistema"):
            mod_para_remover = st.selectbox("Modelo para EXCLUIR", sorted(df_est['Modelo'].unique()), key="del_mod_sel")
            st.error(f"⚠️ Atenção: A exclusão de '{mod_para_remover}' é irreversível.")
            if st.button("Confirmar Exclusão Definitiva"):
                df_pos_del = df_est[df_est['Modelo'] != mod_para_remover]
                if salvar_seguro("Estoque", df_pos_del):
                    st.success("Modelo removido.")
                    st.rerun()
    else:
        st.info("O estoque está vazio. Cadastre seu primeiro modelo na aba ao lado.")

# --- ABA 2: NOVOS MODELOS ---
with tabs[1]:
    st.subheader("✨ Cadastrar Novo Modelo de Chinelo")
    with st.form("form_novo_modelo", clear_on_submit=True):
        novo_nome = st.text_input("Nome/Descrição do Modelo")
        btn_novo = st.form_submit_button("Salvar Modelo no Banco")
        
        if btn_novo:
            if novo_nome:
                # Verifica duplicidade
                if not df_est.empty and novo_nome in df_est['Modelo'].values:
                    st.error("Este modelo já existe no sistema.")
                else:
                    nova_linha = {"Modelo": novo_nome}
                    nova_linha.update({t: 0 for t in TAMANHOS_PADRAO})
                    df_novo_estoque = pd.concat([df_est, pd.DataFrame([nova_linha])], ignore_index=True)
                    if salvar_seguro("Estoque", df_novo_estoque):
                        st.success(f"Modelo '{novo_nome}' cadastrado com sucesso!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("O nome do modelo não pode estar em branco.")

# --- ABA 3: VENDAS ---
with tabs[2]:
    st.subheader("🛒 Realizar Venda")
    col_v1, col_v2 = st.columns([1, 1])
    
    with col_v1:
        if not df_est.empty:
            v_cliente = st.selectbox("Cliente", sorted(list(df_cli['Nome'].unique())) + ["Consumidor Avulso"], key="v_cli")
            v_modelo = st.selectbox("Modelo", sorted(df_est['Modelo'].unique()), key="v_mod")
            v_tamanho = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
            v_preco = st.number_input("Preço de Venda Unitário (R$)", min_value=0.0, step=0.50)
            v_quantidade = st.number_input("Quantidade Vendida", min_value=1, step=1)
            
            if st.button("➕ Adicionar ao Carrinho"):
                if 'carrinho' not in st.session_state: st.session_state.carrinho = []
                st.session_state.carrinho.append({
                    "Modelo": v_modelo, "Tam": v_tamanho, 
                    "Qtd": v_quantidade, "Preco": v_preco
                })
                st.rerun()
        else:
            st.error("Cadastre modelos no estoque antes de vender.")

    with col_v2:
        if 'carrinho' in st.session_state and st.session_state.carrinho:
            st.write("### 🛍️ Carrinho Atual")
            total_venda = 0
            resumo_venda = []
            for i, item in enumerate(st.session_state.carrinho):
                subtotal = item['Preco'] * item['Qtd']
                total_venda += subtotal
                st.write(f"{i+1}. **{item['Modelo']}** ({item['Tam']}) x{item['Qtd']} - R$ {subtotal:.2f}")
                resumo_venda.append(f"{item['Modelo']}({item['Tam']}x{item['Qtd']})")
            
            st.divider()
            st.write(f"**TOTAL: R$ {total_venda:.2f}**")
            
            c_v1, c_v2 = st.columns(2)
            if c_v1.button("🗑️ Limpar Tudo"):
                st.session_state.carrinho = []
                st.rerun()
            
            if c_v2.button("🏁 Finalizar Venda", type="primary"):
                df_venda_est = df_est.copy()
                # Baixa no estoque
                for item in st.session_state.carrinho:
                    idx = df_venda_est.index[df_venda_est['Modelo'] == item['Modelo']][0]
                    v_orig = df_venda_est.at[idx, item['Tam']]
                    estoque_atual = int(float(v_orig)) if v_orig != "" and not pd.isna(v_orig) else 0
                    df_venda_est.at[idx, item['Tam']] = estoque_atual - item['Qtd']
                
                if salvar_seguro("Estoque", df_venda_est):
                    # Registro no extrato
                    nova_venda_ext = pd.DataFrame([{
                        "Data": get_data_hora(),
                        "Cliente": v_cliente,
                        "Resumo": " | ".join(resumo_venda),
                        "Valor Total": total_venda,
                        "Status Pagto": "Pago"
                    }])
                    salvar_seguro("Pedidos", pd.concat([df_ped, nova_venda_ext], ignore_index=True))
                    st.session_state.carrinho = []
                    st.success("Venda concluída!")
                    time.sleep(1)
                    st.rerun()

# --- ABA 4: INSUMOS ---
with tabs[3]:
    st.subheader("🛠️ Gastos e Insumos")
    with st.form("form_insumos", clear_on_submit=True):
        desc_insumo = st.text_input("Descrição do Gasto (ex: Cola, Correias)")
        valor_insumo = st.number_input("Valor Pago (R$)", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            novo_ins = pd.DataFrame([{
                "Data": get_data_hora(),
                "Descricao": desc_insumo,
                "Valor": valor_insumo
            }])
            if salvar_seguro("Insumos", pd.concat([df_ins, novo_ins], ignore_index=True)):
                st.success("Gasto registrado!")
                st.rerun()
    st.dataframe(df_ins, use_container_width=True, hide_index=True)

# --- ABA 5: CLIENTES ---
with tabs[4]:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("form_clientes", clear_on_submit=True):
        c_nome = st.text_input("Nome do Cliente/Loja")
        c_loja = st.text_input("Nome da Loja (Opcional)")
        c_cidade = st.text_input("Cidade")
        c_fone = st.text_input("WhatsApp/Telefone")
        if st.form_submit_button("Salvar Cliente"):
            novo_cli = pd.DataFrame([{
                "Nome": c_nome, "Loja": c_loja, 
                "Cidade": c_cidade, "Telefone": c_fone
            }])
            if salvar_seguro("Clientes", pd.concat([df_cli, novo_cli], ignore_index=True)):
                st.success("Cliente salvo!")
                st.rerun()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

# --- ABA 6: EXTRATO ---
with tabs[5]:
    st.subheader("🧾 Histórico de Movimentações")
    if not df_ped.empty:
        # Mostra do mais recente para o mais antigo
        df_extrato_view = df_ped.iloc[::-1]
        for idx, row in df_extrato_view.iterrows():
            with st.container(border=True):
                c_ex1, c_ex2, c_ex3 = st.columns([0.15, 0.7, 0.15])
                c_ex1.write(f"**{row['Data']}**")
                c_ex2.write(f"**{row['Cliente']}** - {row['Resumo']}")
                c_ex2.write(f"Valor: R$ {limpar_valor(row['Valor Total']):.2f}")
                
                # Botões de ação
                if c_ex3.button("🗑️", key=f"del_ext_{idx}"):
                    if salvar_seguro("Pedidos", df_ped.drop(idx)):
                        st.rerun()
                
                pdf_data = gerar_recibo(row)
                if pdf_data:
                    c_ex3.download_button("📄 PDF", data=pdf_data, file_name=f"recibo_{idx}.pdf", key=f"pdf_{idx}")
    else:
        st.info("Nenhuma movimentação registrada.")

# --- ABA 7: LEMBRETES ---
with tabs[6]:
    st.subheader("📅 Contas e Lembretes")
    with st.form("form_lembrete", clear_on_submit=True):
        l_nome = st.text_input("Título do Lembrete")
        l_venc = st.date_input("Data de Vencimento")
        l_valor = st.number_input("Valor previsto (R$)", min_value=0.0)
        if st.form_submit_button("Agendar"):
            novo_lem = pd.DataFrame([{
                "Data": get_data_hora(),
                "Nome": l_nome,
                "Vencimento": str(l_venc),
                "Valor": l_valor
            }])
            if salvar_seguro("Lembretes", pd.concat([df_lem, novo_lem], ignore_index=True)):
                st.success("Lembrete agendado!")
                st.rerun()
    
    st.divider()
    if not df_lem.empty:
        for idx, row in df_lem.iterrows():
            col_l1, col_l2 = st.columns([0.8, 0.2])
            col_l1.write(f"📌 **{row['Nome']}** | Vence em: {row['Vencimento']} | R$ {row['Valor']}")
            if col_l2.button("Concluir ✅", key=f"lem_ok_{idx}"):
                if salvar_seguro("Lembretes", df_lem.drop(idx)):
                    st.rerun()
