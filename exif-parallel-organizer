import streamlit as st
import os
import sys
import re
from crewai import Agent, Task, Crew, Process, LLM

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Pasukan AI Qwen - Tempatan",
    page_icon="🛡️",
    layout="wide"
)

# --- 2. FUNGSI PEMBANTU ---
class StreamToExpander:
    def __init__(self, expander):
        self.expander = expander
        self.buffer = []
        self.colors = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def write(self, data):
        clean_data = self.colors.sub('', data)
        if clean_data.strip():
            self.buffer.append(clean_data)
            self.expander.code("\n".join(self.buffer[-15:]), language="text")

    def flush(self):
        pass

def extract_python_code(text):
    pattern = r'```python\n(.*?)```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    else:
        return "# Tiada blok kod Python dijumpai."

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🎛️ Pusat Kawalan")
    
    # PILIHAN MOD OPERASI (BARU)
    st.subheader("1. Mod Operasi")
    mod_operasi = st.radio(
        "Apa anda nak buat?",
        ["✨ Jana Kod Baru", "🔍 Review Kod Lama"],
        captions=["Buat projek dari kosong", "Audit kod sedia ada"]
    )
    
    st.divider()

    st.subheader("2. Enjin AI")
    model_name = st.text_input("Model Ollama", value="ollama/qwen3:8b")
    
    st.subheader("3. Gaya Bahasa")
    nada = st.selectbox(
        "Pilih Mood Ejen:",
        ["Formal (Korporat)", "Santai (Bro/Sis)", "Garang (Senior Lead)"],
        index=2 # Default Garang untuk Review
    )

    if nada == "Santai (Bro/Sis)":
        gaya_bahasa = "Gunakan bahasa santai, panggil pengguna 'Bro'. Guna analogi mudah."
    elif nada == "Garang (Senior Lead)":
        gaya_bahasa = "Sangat tegas, kritikal, dan pedas. Cari kesalahan sekecil kuman. Jangan berkias."
    else:
        gaya_bahasa = "Gunakan Bahasa Melayu baku, profesional, dan sopan."

    # Profil Pasukan (Kemaskini ikut Mod)
    st.divider()
    st.subheader("4. Profil Pasukan")
    with st.expander("Lihat Ahli Pasukan", expanded=True):
        if mod_operasi == "✨ Jana Kod Baru":
            st.info("**🧑‍💻 Jurutaip Kod**\n\nMenulis skrip baru.")
            st.warning("**🕵️ QA**\n\nSemak kod Jurutaip.")
        else:
            st.warning("**🕵️ QA (Lead)**\n\nAnalisa kod pengguna.")
            st.info("**🧑‍💻 Jurutaip Kod**\n\nBaiki kod pengguna.")
            
        st.success("**📝 Penulis Teknikal**\n\nBuat laporan.")

# --- 4. UI UTAMA ---
st.title(f"🛡️ Pasukan AI: {mod_operasi}")

def main():
    
    inputs = {}
    
    # UI BERUBAH IKUT MOD
    if mod_operasi == "✨ Jana Kod Baru":
        user_input = st.text_area("🎯 Masukkan Idea Projek:", height=100, 
                             placeholder="Contoh: Buat script game Snake...")
        tombol_teks = "🚀 JANA KOD"
    else:
        user_input = st.text_area("🐍 Tampal Kod Python Anda Di Sini:", height=200, 
                             placeholder="def fungsi_saya():\n    pass...")
        tombol_teks = "🔍 AUDIT KOD SAYA"

    col1, col2 = st.columns([1, 5])
    with col1:
        start_btn = st.button(tombol_teks, type="primary", use_container_width=True)

    if start_btn and user_input:
        
        os.environ["OPENAI_API_KEY"] = "NA"
        os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
        os.environ["OTEL_SDK_DISABLED"] = "true"
        
        with st.status("🤖 Sedang Memproses...", expanded=True) as status:
            st.write("🔌 Menghubungkan ke Neural Network...")
            log_expander = st.expander("Log Terminal Live", expanded=True)
            
            try:
                my_llm = LLM(model=model_name, base_url="http://localhost:11434")

                # --- DEFINISI EJEN ---
                coder = Agent(
                    role='Senior Python Developer',
                    goal='Menulis kod Python bertaraf dunia (World Class).',
                    backstory=f"Pakar refactoring. {gaya_bahasa} Anda membaiki kod buruk menjadi seni.",
                    llm=my_llm, verbose=True
                )

                qa = Agent(
                    role='Security & Logic Auditor',
                    goal='Mencari bug, celah keselamatan, dan kod yang tidak efisien.',
                    backstory=f"Auditor kod yang kejam. {gaya_bahasa} Anda tidak teragak-agak mengkritik kod pengguna.",
                    llm=my_llm, verbose=True
                )

                writer = Agent(
                    role='Technical Report Writer',
                    goal='Menyediakan laporan bedah siasat kod.',
                    backstory=f"Pakar dokumentasi. {gaya_bahasa}",
                    llm=my_llm, verbose=True
                )

                # --- LOGIK TUGASAN BERUBAH IKUT MOD ---
                tasks_list = []
                
                if mod_operasi == "✨ Jana Kod Baru":
                    # Aliran: Coder -> QA -> Writer
                    task1 = Task(description=f"Tulis kod untuk: {user_input}", expected_output="Kod Python.", agent=coder)
                    task2 = Task(description="Semak kod Coder.", expected_output="Kod lulus QA.", agent=qa, context=[task1])
                    task3 = Task(description="Buat dokumentasi.", expected_output="Markdown.", agent=writer, context=[task2])
                    tasks_list = [task1, task2, task3]
                    
                else: 
                    # MOD REVIEW: QA -> Coder -> Writer
                    # 1. QA Baca Kod Pengguna Dulu
                    task1 = Task(
                        description=f"Analisa kod pengguna ini baris demi baris:\n```python\n{user_input}\n```\nSenaraikan SEMUA bug, risiko sekuriti, dan gaya penulisan yang buruk.",
                        expected_output="Senarai kesalahan kod dalam point form.",
                        agent=qa
                    )
                    
                    # 2. Coder Baiki Kod Tu
                    task2 = Task(
                        description="Berdasarkan kritikan QA, tulis semula kod pengguna supaya menjadi versi yang 'Perfect'.",
                        expected_output="Kod Python Versi 2.0 yang telah dibaiki sepenuhnya.",
                        agent=coder,
                        context=[task1]
                    )
                    
                    # 3. Writer Buat Laporan
                    task3 = Task(
                        description="Bina laporan 'Code Review'. Masukkan: 1. Apa yang salah dulu. 2. Apa yang dah dibaiki. 3. Kod penuh baru.",
                        expected_output="Laporan Markdown.",
                        agent=writer,
                        context=[task1, task2]
                    )
                    tasks_list = [task1, task2, task3]

                # --- JALANKAN CREW ---
                crew = Crew(
                    agents=[qa, coder, writer],
                    tasks=tasks_list,
                    verbose=True,
                    process=Process.sequential
                )

                # Hijack Terminal
                sys.stdout = StreamToExpander(log_expander)
                result = crew.kickoff()
                sys.stdout = sys.__stdout__ # Reset
                
                status.update(label="✅ Siap!", state="complete", expanded=False)

                # --- PAPARAN HASIL ---
                st.divider()
                
                kod_python = extract_python_code(str(result))
                
                tab1, tab2 = st.tabs(["📄 Laporan Review", "✨ Kod Baru (.py)"])
                
                with tab1:
                    st.markdown(result)
                    
                with tab2:
                    if mod_operasi == "🔍 Review Kod Lama":
                        st.caption("Ini adalah versi kod anda yang telah dibaiki:")
                    st.code(kod_python, language='python')

            except Exception as e:
                sys.stdout = sys.__stdout__
                st.error(f"Ralat: {e}")

if __name__ == "__main__":
    main()
