import os
import streamlit as st
from utils.auth import Auth
from services.pdf_service import PDFService


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def list_pdfs(base: str):
    for root, _, files in os.walk(base):
        for f in files:
            if f.lower().endswith('.pdf'):
                yield os.path.join(root, f)


def run_instructor_page():
    st.title("Instructor Uploads")

    if 'user_id' not in st.session_state or not st.session_state.user_id:
        st.warning("Please log in to access this page.")
        return
    if not Auth.is_instructor(st.session_state.user_id):
        st.error("You do not have permission to view this page.")
        return

    pdf_service = PDFService()

    st.subheader("Upload PDFs by Course/Week")
    with st.form("upload_form"):
        course = st.text_input("Course (e.g., PHIL101)")
        week = st.text_input("Week (e.g., Week01)")
        uploads = st.file_uploader("Select PDFs", type=["pdf"], accept_multiple_files=True)
        submitted = st.form_submit_button("Upload")

    if submitted:
        if not course or not week or not uploads:
            st.error("Course, Week, and at least one PDF are required.")
        else:
            target_dir = os.path.join('Readings', course, week)
            ensure_dir(target_dir)
            saved = 0
            for f in uploads:
                try:
                    dest = os.path.join(target_dir, f.name)
                    with open(dest, 'wb') as out:
                        out.write(f.read())
                    saved += 1
                except Exception as e:
                    st.error(f"Failed to save {f.name}: {str(e)}")
            if saved:
                st.success(f"Uploaded {saved} file(s) to {target_dir}")

    st.subheader("Current Library")
    base = 'Readings'
    if not os.path.exists(base):
        st.info("No Readings directory yet.")
        return

    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        filter_course = st.text_input("Filter by Course", value="")
    with col_filter2:
        filter_week = st.text_input("Filter by Week", value="")

    rows = []
    for path in list_pdfs(base):
        rel = os.path.relpath(path, base)
        parts = rel.split(os.sep)
        course = parts[0] if len(parts) > 2 else ""
        week = parts[1] if len(parts) > 2 else ""
        fname = parts[-1]
        if filter_course and course and filter_course.lower() not in course.lower():
            continue
        if filter_week and week and filter_week.lower() not in week.lower():
            continue
        rows.append((course, week, fname, path))

    if not rows:
        st.info("No PDFs found matching the filter.")
        return

    for course, week, fname, path in rows:
        with st.container():
            st.write(f"Course: **{course or '-'}** | Week: **{week or '-'}** | File: {fname}")
            cols = st.columns(3)
            with cols[0]:
                if st.button("Summarize (cache)", key=f"sum_{path}"):
                    # Trigger summary generation for this single file using service internals
                    try:
                        # Private call path: reuse extract and summary generation
                        text = pdf_service._extract_text_with_fallback(path)  # noqa: SLF001
                        if text.strip():
                            summary = pdf_service._generate_summary(text, fname)  # noqa: SLF001
                            file_hash = pdf_service._calculate_file_hash(path)  # noqa: SLF001
                            cache_key = f"summary_{file_hash}"
                            with pdf_service._cache_lock:  # noqa: SLF001
                                pdf_service.summary_cache[cache_key] = summary
                            pdf_service._write_summary_to_disk(file_hash, summary)  # noqa: SLF001
                            st.success("Summary cached.")
                        else:
                            st.warning("No text extracted from PDF.")
                    except Exception as e:
                        st.error(f"Error summarizing: {str(e)}")
            with cols[1]:
                if st.button("Clear cache", key=f"clr_{path}"):
                    try:
                        file_hash = pdf_service._calculate_file_hash(path)  # noqa: SLF001
                        p = os.path.join('.cache', 'summaries', f"{file_hash}.txt")
                        if os.path.exists(p):
                            os.remove(p)
                        st.success("Cache cleared (disk). Memory cache will clear on restart.")
                    except Exception as e:
                        st.error(f"Error clearing cache: {str(e)}")
            with cols[2]:
                st.write(" ")
                st.caption(path)


if __name__ == "__main__":
    run_instructor_page()

