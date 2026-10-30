import streamlit as st
import json
import os
import smtplib
from email.message import EmailMessage
from PIL import Image
import io

RM_FILE = "rms.json"
DOC_TYPES_FILE = "doc_types.json"
FO_CC_EMAIL = "fo.cs@ke.com.pk"

DEFAULT_RMS = {
    "RM Farhan": "farhan@example.com",
    "RM Tariq": "tariq@example.com",
    "RM Asad": "asad@example.com"
}

DEFAULT_DOC_TYPES = [
    "Application Form",
    "Payment Receipt",
    "CNIC Copy",
    "Ownership / Rent Deed",
    "Site Verification",
    "Load Sanction Letter",
    "General Correspondence"
]

def load_data(file_path, default_val):
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump(default_val, f, indent=4)
        return default_val
    with open(file_path, "r") as f:
        return json.load(f)

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

def send_email_with_pdf(sender_email, app_password, recipient_email, rm_name, case_id, case_name, doc_type, pdf_bytes, filename):
    msg = EmailMessage()
    msg['Subject'] = f"[{doc_type}] Case: {case_id} - {case_name}"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Cc'] = FO_CC_EMAIL

    body_text = f"""Dear {rm_name},

Please find attached the scanned document received at the Front Office desk.

• Case ID: {case_id}
• Consumer / Case Name: {case_name}
• Document Type: {doc_type}
• Dispatched By: Front Office Counter

Best regards,
Front Office Operations
"""
    msg.set_content(body_text)

    msg.add_attachment(
        pdf_bytes,
        maintype='application',
        subtype='pdf',
        filename=filename
    )

    # Deliver to both recipient and CC
    recipients = [recipient_email, FO_CC_EMAIL]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.send_message(msg, to_addrs=recipients)

st.set_page_config(page_title="FO Document Dispatcher", page_icon="📑", layout="centered")

sender_email = st.secrets.get("SENDER_EMAIL", "")
app_password = st.secrets.get("APP_PASSWORD", "")

tab_scan, tab_manage = st.tabs(["📷 Mobile Scan & Dispatch", "⚙️ Directory & Doc Types"])

if "scanned_pages" not in st.session_state:
    st.session_state.scanned_pages = []
if "last_snapped_id" not in st.session_state:
    st.session_state.last_snapped_id = None

with tab_scan:
    st.header("Front Office Case Dispatch")

    rms = load_data(RM_FILE, DEFAULT_RMS)
    doc_types = load_data(DOC_TYPES_FILE, DEFAULT_DOC_TYPES)

    col1, col2 = st.columns(2)
    with col1:
        case_id = st.text_input("Case ID *", placeholder="e.g., 2026-10492")
    with col2:
        case_name = st.text_input("Case / Consumer Name *", placeholder="e.g., Diamond Mills")

    col3, col4 = st.columns(2)
    with col3:
        selected_doc_type = st.selectbox("Document Type *", doc_types if doc_types else ["General Document"])
    with col4:
        selected_rm = st.selectbox("Select Relationship Manager (RM) *", list(rms.keys()) if rms else ["No RMs Configured"])
    
    rm_email = rms.get(selected_rm, "")
    st.caption(f"📧 Destination: **{rm_email}** | CC: **{FO_CC_EMAIL}**")

    st.markdown("---")

    # In-memory browser camera feed (does not download to phone gallery)
    camera_photo = st.camera_input("Point camera and take photo")

    if camera_photo is not None:
        photo_id = camera_photo.file_id
        if st.session_state.last_snapped_id != photo_id:
            img = Image.open(camera_photo).convert("RGB")
            st.session_state.scanned_pages.append(img)
            st.session_state.last_snapped_id = photo_id

    total_pages = len(st.session_state.scanned_pages)
    if total_pages > 0:
        c_info, c_reset = st.columns([3, 1])
        c_info.success(f"📄 **{total_pages}** page(s) ready in memory.")
        if c_reset.button("🔄 Discard / Retake"):
            st.session_state.scanned_pages.clear()
            st.session_state.last_snapped_id = None
            st.rerun()

    st.markdown("---")

    if st.button("🚀 Send to RM Instantly", type="primary", use_container_width=True):
        if not case_id.strip() or not case_name.strip():
            st.error("Please enter both Case ID and Case / Consumer Name.")
        elif total_pages == 0:
            st.error("Please capture at least one page with the camera first.")
        elif not rm_email:
            st.error("Selected RM has no valid email address.")
        else:
            with st.spinner("Compiling PDF and dispatching to RM & Front Office CC..."):
                try:
                    c_id = case_id.strip().replace(" ", "_").replace("/", "-")
                    c_name = case_name.strip().replace(" ", "_")
                    d_type = selected_doc_type.strip().replace(" ", "_").replace("/", "-")
                    output_pdf_filename = f"{c_id}_{d_type}_{c_name}.pdf"

                    # Process in RAM only
                    pdf_buffer = io.BytesIO()
                    pages = st.session_state.scanned_pages
                    pages[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pages[1:])
                    pdf_bytes = pdf_buffer.getvalue()

                    send_email_with_pdf(
                        sender_email=sender_email,
                        app_password=app_password,
                        recipient_email=rm_email,
                        rm_name=selected_rm,
                        case_id=case_id.strip(),
                        case_name=case_name.strip(),
                        doc_type=selected_doc_type,
                        pdf_bytes=pdf_bytes,
                        filename=output_pdf_filename
                    )

                    st.success(f"✅ Dispatched **{output_pdf_filename}** ({total_pages} pages) to **{selected_rm}** ({rm_email}) and CC to **{FO_CC_EMAIL}**!")
                    
                    # Purge buffer and cache immediately from memory
                    st.session_state.scanned_pages.clear()
                    st.session_state.last_snapped_id = None
                except Exception as e:
                    st.error(f"Error while dispatching: {e}")

with tab_manage:
    st.header("Directory & Document Type Settings")
    
    # Document Types Management
    st.subheader("1. Manage Document Types")
    doc_types = load_data(DOC_TYPES_FILE, DEFAULT_DOC_TYPES)
    
    col_d1, col_d2 = st.columns([3, 1])
    with col_d1:
        new_doc_type = st.text_input("New Document Type", placeholder="e.g., Bank Guarantee")
    with col_d2:
        st.write("")
        st.write("")
        if st.button("➕ Add Doc Type"):
            if new_doc_type.strip() and new_doc_type.strip() not in doc_types:
                doc_types.append(new_doc_type.strip())
                save_data(DOC_TYPES_FILE, doc_types)
                st.rerun()

    for idx, dt in enumerate(doc_types):
        c_dt1, c_dt2 = st.columns([5, 1])
        c_dt1.write(f"• {dt}")
        if c_dt2.button("🗑️", key=f"del_dt_{idx}"):
            doc_types.remove(dt)
            save_data(DOC_TYPES_FILE, doc_types)
            st.rerun()

    st.markdown("---")

    # RM Directory Management
    st.subheader("2. Manage Relationship Managers")
    rms = load_data(RM_FILE, DEFAULT_RMS)

    col_rm1, col_rm2 = st.columns(2)
    with col_rm1:
        new_rm_name = st.text_input("RM Name", placeholder="e.g., RM Naveed")
    with col_rm2:
        new_rm_email = st.text_input("RM Email", placeholder="e.g., naveed@example.com")

    if st.button("➕ Save RM"):
        if new_rm_name.strip() and new_rm_email.strip():
            rms[new_rm_name.strip()] = new_rm_email.strip()
            save_data(RM_FILE, rms)
            st.rerun()

    for name, email in list(rms.items()):
        c1, c2, c3 = st.columns([3, 4, 1])
        c1.write(f"**{name}**")
        c2.write(email)
        if c3.button("🗑️", key=f"del_rm_{name}"):
            del rms[name]
            save_data(RM_FILE, rms)
            st.rerun()