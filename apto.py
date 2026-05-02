import streamlit as st
from supabase import create_client, Client
import uuid

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://dygisihrrhlseadmatyw.supabase.co"
SUPABASE_KEY = "sb_publishable_3MrkEx1y1VUNFmH9KJ8QVQ_SuppvyGw"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Gestión de Obras Pro", layout="wide")

# Estilos para efectos visuales
st.markdown("""
    <style>
    .zoom { transition: transform .3s; border-radius: 8px; cursor: pointer; }
    .zoom:hover { transform: scale(1.15); z-index: 100; position: relative; }
    .card { padding: 15px; border: 1px solid #eee; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)


# --- FUNCIONES DE SOPORTE ---
def upload_imgs(files, arreglo_id, tipo):
    for file in files:
        ext = file.name.split('.')[-1]
        path = f"{tipo}/{arreglo_id}/{uuid.uuid4()}.{ext}"
        supabase.storage.from_("obras_images").upload(path, file.getvalue(), {"content-type": file.type})
        url = supabase.storage.from_("obras_images").get_public_url(path)
        supabase.table("fotos_arreglo").insert({"arreglo_id": arreglo_id, "url_foto": url, "tipo_foto": tipo}).execute()

# --- DIÁLOGO PARA VER IMAGEN ---
@st.dialog("Vista Previa")
def ver_imagen(url, foto_id, storage_path):
    st.image(url, use_container_width=True)
    if st.button("🗑️ Eliminar Permanente", type="primary"):
        # 1. Borrar de la tabla
        supabase.table("fotos_arreglo").delete().eq("id", foto_id).execute()
        # 2. Borrar del Storage (extrayendo el path relativo)
        # Nota: el path debe ser el relativo dentro del bucket
        path_in_storage = url.split("public/obras_images/")[-1]
        supabase.storage.from_("obras_images").remove([path_in_storage])
        st.success("Foto eliminada.")
        st.rerun()


# --- INTERFAZ ---
st.title("🚧 Control de Obras y Propuestas Granulares")

menu = ["Obras y Arreglos", "Proveedores", "Nueva Obra"]
choice = st.sidebar.selectbox("Navegación", menu)

if choice == "Nueva Obra":
    with st.form("c_obra"):
        t = st.selectbox("Tipo", ["Residencial", "Comercial"])
        d = st.text_input("Dirección Exacta")
        if st.form_submit_button("Crear Proyecto"):
            supabase.table("construcciones").insert({"tipo": t, "direccion": d, "usuario_id": "admin"}).execute()
            st.success("Obra registrada.")

elif choice == "Obras y Arreglos":
    obras = supabase.table("construcciones").select("*").execute()
    
    for obra in obras.data:
        with st.expander(f"📍 {obra['direccion']}"):
            # Añadir Partes
            new_p = st.text_input("Añadir Sitio (ej. Cocina)", key=f"np_{obra['id']}")
            if st.button("Guardar Sitio", key=f"bp_{obra['id']}"):
                supabase.table("partes").insert({"obra_id": obra['id'], "nombre": new_p}).execute()
                st.rerun()

            partes = supabase.table("partes").select("*").eq("obra_id", obra['id']).execute()
            for p in partes.data:
                st.subheader(f"🚪 {p['nombre']}")
                
                # Formulario para Arreglos
                with st.form(f"f_arr_{p['id']}"):
                    desc = st.text_input("¿Qué hay que arreglar?")
                    costo_e = st.number_input("Presupuesto base ($)", min_value=0.0)
                    c1, c2 = st.columns(2)
                    im_a = c1.file_uploader("Fotos Antes", accept_multiple_files=True, key=f"ua_{p['id']}")
                    im_d = c2.file_uploader("Fotos Después", accept_multiple_files=True, key=f"ud_{p['id']}")
                    
                    if st.form_submit_button("Registrar Arreglo"):
                        res = supabase.table("arreglos").insert({"parte_id": p['id'], "descripcion_arreglo": desc, "costo_estimado": costo_e}).execute()
                        a_id = res.data[0]['id']
                        if im_a: upload_imgs(im_a, a_id, "antes")
                        if im_d: upload_imgs(im_d, a_id, "despues")
                        st.rerun()

                # Mostrar Arreglos y sus Propuestas
                arreglos = supabase.table("arreglos").select("*").eq("parte_id", p['id']).execute()
                for a in arreglos.data:
                    st.markdown(f'<div class="card"><b>Tarea:</b> {a["descripcion_arreglo"]} | <b>Presupuesto:</b> ${a["costo_estimado"]}</div>', unsafe_allow_html=True)
                    
                    # Mostrar Fotos
                    fotos = supabase.table("fotos_arreglo").select("*").eq("arreglo_id", a['id']).execute()
                    f_a = [f['url_foto'] for f in fotos.data if f['tipo_foto'] == 'antes']
                    f_d = [f['url_foto'] for f in fotos.data if f['tipo_foto'] == 'despues']
                    
                    c_a, c_d = st.columns(2)
                    if f_a: 
                        c_a.caption("Estado Inicial")
                        cols = c_a.columns(3)
                        for i, u in enumerate(f_a): cols[i%3].markdown(f'<img src="{u}" class="zoom" width="100%">', unsafe_allow_html=True)
                    if f_d: 
                        c_d.caption("Resultado")
                        cols = c_d.columns(3)
                        for i, u in enumerate(f_d): cols[i%3].markdown(f'<img src="{u}" class="zoom" width="100%">', unsafe_allow_html=True)
                    
                    # Ver Propuestas de Proveedores para ESTE arreglo
                    props = supabase.table("propuestas").select("*, proveedores(nombre_empresa)").eq("arreglo_id", a['id']).execute()
                    if props.data:
                        st.write("📋 **Propuestas recibidas:**")
                        for pr in props.data:
                            st.caption(f"Propuesta de {pr['proveedores']['nombre_empresa']}: ${pr['monto_propuesto']} - {pr['estado_propuesta']}")

elif choice == "Proveedores":
    st.header("Portal de Proveedores")
    provs = supabase.table("proveedores").select("*").execute()
    
    # Formulario para enviar propuesta a un arreglo específico
    st.subheader("Enviar nueva cotización")
    all_arr = supabase.table("arreglos").select("id, descripcion_arreglo, partes(nombre, construcciones(direccion))").execute()
    
    if all_arr.data and provs.data:
        with st.form("f_prop"):
            sel_prov = st.selectbox("Proveedor", provs.data, format_func=lambda x: x['nombre_empresa'])
            sel_arr = st.selectbox("Arreglo específico", all_arr.data, 
                                   format_func=lambda x: f"{x['descripcion_arreglo']} ({x['partes']['nombre']} en {x['partes']['construcciones']['direccion']})")
            monto = st.number_input("Tu oferta ($)", min_value=0.0)
            if st.form_submit_button("Enviar Oferta"):
                supabase.table("propuestas").insert({"arreglo_id": sel_arr['id'], "proveedor_id": sel_prov['id'], "monto_propuesto": monto}).execute()
                st.success("Propuesta vinculada al arreglo.")

# --- VISUALIZACIÓN DE FOTOS CON CLICK ---
def mostrar_galeria(arreglo_id, tipo):
    fotos = supabase.table("fotos_arreglo").select("*").eq("arreglo_id", arreglo_id).eq("tipo_foto", tipo).execute()
    if fotos.data:
        cols = st.columns(4)
        for i, f in enumerate(fotos.data):
            with cols[i % 4]:
                # Usamos un botón con imagen o el estilo zoom
                st.markdown(f'<img src="{f["url_foto"]}" style="width:100%; border-radius:5px; cursor:pointer;">', unsafe_allow_html=True)
                if st.button("🔍 Ver/Borrar", key=f"btn_{f['id']}"):
                    ver_imagen(f['url_foto'], f['id'], f['url_foto'])

# --- SECCIÓN PROVEEDORES ---
st.divider()
st.header("🤝 Gestión de Proveedores")

with st.expander("Registrar Nuevo Proveedor"):
    with st.form("nuevo_prov"):
        nombre = st.text_input("Nombre de Empresa / Profesional")
        especialidad = st.text_input("Especialidad (ej. Plomería)")
        if st.form_submit_button("Registrar"):
            supabase.table("proveedores").insert({"nombre_empresa": nombre, "especialidad": especialidad}).execute()
            st.success("Proveedor registrado")
            st.rerun()

# Mostrar proveedores y sus propuestas
provs = supabase.table("proveedores").select("*").execute()
if provs.data:
    for p in provs.data:
        st.write(f"**{p['nombre_empresa']}** - {p['especialidad']}")
        # Aquí puedes añadir un selectbox para asignar este proveedor a un arreglo
