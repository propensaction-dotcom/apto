import streamlit as st
from supabase import create_client, Client
import uuid

# --- 1. CONFIGURACIÓN INICIAL Y CONEXIÓN ---
SUPABASE_URL = "https://dygisihrrhlseadmatyw.supabase.co"
SUPABASE_KEY = "sb_publishable_3MrkEx1y1VUNFmH9KJ8QVQ_SuppvyGw"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Exoesqueleto Constructora", layout="wide")

# --- 2. MANEJO DE SESIÓN Y AUTH ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_sidebar():
    with st.sidebar:
        if st.session_state.user is None:
            st.subheader("Acceso al Sistema")
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            col1, col2 = st.columns(2)
            if col1.button("Entrar"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.rerun()
                except:
                    st.error("Credenciales inválidas")
            if col2.button("Registrar"):
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.info("Confirma tu email para activar la cuenta.")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.write(f"Conectado: **{st.session_state.user.email}**")
            if st.button("Cerrar Sesión"):
                supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()

login_sidebar()

if not st.session_state.user:
    st.title("🏗️ Gestión de Obras")
    st.warning("Inicia sesión para gestionar el proyecto.")
    st.stop()

# --- 3. OBTENCIÓN DE ROL ---
try:
    perfil = supabase.table("perfiles").select("rol").eq("id", st.session_state.user.id).single().execute()
    user_rol = perfil.data["rol"] if perfil.data else "usuario"
except:
    user_rol = "usuario"

# --- 4. FUNCIONES DE APOYO (MODALES Y GALERÍA) ---

@st.dialog("Detalle de Imagen")
def ver_imagen_modal(url, foto_id):
    st.image(url, use_container_width=True)
    if user_rol == "admin":
        if st.button("🗑️ Eliminar Permanente", type="primary"):
            # Borrar de DB
            supabase.table("fotos_arreglo").delete().eq("id", foto_id).execute()
            # Borrar de Storage
            path_in_storage = url.split("public/obras_images/")[-1]
            supabase.storage.from_("obras_images").remove([path_in_storage])
            st.success("Eliminada.")
            st.rerun()

def mostrar_galeria(arreglo_id, tipo):
    fotos = supabase.table("fotos_arreglo").select("*").eq("arreglo_id", arreglo_id).eq("tipo_foto", tipo).execute()
    if fotos.data:
        cols = st.columns(4)
        for i, f in enumerate(fotos.data):
            with cols[i % 4]:
                st.image(f["url_foto"], use_container_width=True)
                if st.button("🔍 Ver", key=f"btn_{f['id']}"):
                    ver_imagen_modal(f['url_foto'], f['id'])

# --- 5. INTERFAZ PRINCIPAL SEGÚN ROL ---

st.title(f"🚀 Dashboard: {user_rol.capitalize()}")

# --- SECCIÓN: OBRAS Y AVANCES ---
st.header("📋 Estado de Obras")

if user_rol == "admin":
    with st.expander("➕ Registrar Nueva Obra"):
        with st.form("nueva_obra"):
            nombre_obra = st.text_input("Nombre del Proyecto")
            if st.form_submit_button("Crear"):
                supabase.table("construcciones").insert({"nombre": nombre_obra}).execute()
                st.success("Obra creada")
                st.rerun()

# Listar Obras
obras = supabase.table("construcciones").select("*").execute()

if obras.data:
    obra_sel = st.selectbox(
        "Selecciona Obra", 
        options=obras.data, 
        format_func=lambda x: x.get("nombre", "Sin nombre")
    )
    
    # Partes de la Obra
    st.subheader(f"Partes de: {obra_sel['nombre']}")
    if user_rol == "admin":
        with st.form("nueva_parte"):
            n_parte = st.text_input("Nombre de la Parte (ej: Baño, Cocina)")
            if st.form_submit_button("Añadir Parte"):
                supabase.table("partes").insert({"construccion_id": obra_sel["id"], "nombre": n_parte}).execute()
                st.rerun()
    
    partes = supabase.table("partes").select("*").eq("construccion_id", obra_sel["id"]).execute()
    for p in partes.data:
        with st.expander(f"📍 {p['nombre']}"):
            # Arreglos dentro de la parte
            arreglos = supabase.table("arreglos").select("*").eq("parte_id", p["id"]).execute()
            for arr in arreglos.data:
                st.markdown(f"**Arreglo:** {arr['descripcion']}")
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Antes")
                    mostrar_galeria(arr["id"], "antes")
                with c2:
                    st.caption("Después")
                    mostrar_galeria(arr["id"], "despues")
                
                if user_rol == "admin":
                    subida = st.file_uploader(f"Subir foto para {arr['descripcion']}", key=f"up_{arr['id']}")
                    t_foto = st.radio("Tipo", ["antes", "despues"], key=f"tipo_{arr['id']}")
                    if st.button("Guardar Foto", key=f"save_{arr['id']}"):
                        if subida:
                            ext = subida.name.split(".")[-1]
                            fname = f"{uuid.uuid4()}.{ext}"
                            res_storage = supabase.storage.from_("obras_images").upload(fname, subida.read())
                            url = f"{SUPABASE_URL}/storage/v1/object/public/obras_images/{fname}"
                            supabase.table("fotos_arreglo").insert({
                                "arreglo_id": arr["id"], "url_foto": url, "tipo_foto": t_foto
                            }).execute()
                            st.rerun()

    else:
        st.info("No hay obras registradas o no tienes permisos para verlas.")
        if user_rol == "admin":
        st.write("Verifica que la tabla 'construcciones' tenga datos y que el RLS esté configurado.")
# --- SECCIÓN: PROVEEDORES Y PROPUESTAS ---
st.divider()
st.header("🤝 Proveedores y Propuestas")

if user_rol in ["admin", "proveedor"]:
    if user_rol == "admin":
        provs = supabase.table("proveedores").select("*").execute()
        st.table(provs.data)
    
    if user_rol == "proveedor":
        with st.form("form_propuesta"):
            st.subheader("Enviar Propuesta")
            monto = st.number_input("Costo Estimado ($)", min_value=0)
            desc = st.text_area("Detalles del servicio")
            if st.form_submit_button("Enviar"):
                # Aquí vincularías a un arreglo_id específico si lo deseas
                supabase.table("propuestas").insert({
                    "proveedor_id": user_id, # Necesitarías lógica para sacar el ID del proveedor
                    "monto": monto,
                    "detalle": desc
                }).execute()
                st.success("Propuesta enviada")
