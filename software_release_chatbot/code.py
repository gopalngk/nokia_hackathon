import os
import re
import uuid
import smtplib
import subprocess
from email.mime.text import MIMEText
from typing import List, Tuple, Optional, Dict
import yaml
import streamlit as st
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip loading .env file
    pass


# =========================
# Configuration
# =========================
def load_config_with_env_vars(config_path: str) -> dict:
    """Load YAML config and substitute environment variables or Streamlit secrets."""
    with open(config_path, "r") as f:
        config_content = f.read()
    
    # Replace ${VAR_NAME} with environment variable values or Streamlit secrets
    def replace_env_var(match):
        var_name = match.group(1)
        
        # Try Streamlit secrets first (for Streamlit Cloud deployment)
        try:
            return st.secrets[var_name]
        except (KeyError, AttributeError):
            pass
        
        # Fall back to environment variables
        return os.getenv(var_name, match.group(0))  # Return original if not found
    
    config_content = re.sub(r'\$\{([^}]+)\}', replace_env_var, config_content)
    return yaml.safe_load(config_content)

cfg_file = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(cfg_file, "code.yml")
CFG = load_config_with_env_vars(cfg_path)

PDF_DIR = CFG["app"]["pdf_dir"]
INDEX_DIR = CFG["app"]["index_dir"]
MAX_RESULTS = CFG["app"]["max_results"]

SCRIPTS_DIR = CFG["scripts"]["base_dir"]

SCRIPTS_DIR = os.path.join(cfg_file, SCRIPTS_DIR)
PDF_DIR = os.path.join(cfg_file, PDF_DIR)
INDEX_DIR = os.path.join(cfg_file, INDEX_DIR)

# Maintainer email config
MAINTAINER_EMAIL = CFG["email"]["maintainer"]
SMTP_HOST = CFG["email"]["smtp_host"]
SMTP_PORT = CFG["email"]["smtp_port"]
SMTP_USER = CFG["email"]["smtp_user"]
SMTP_PASS = CFG["email"]["smtp_pass"]
SMTP_SENDER = CFG["email"]["sender"]



# PDF chunking
CHUNK_SIZE = 800  # chars
CHUNK_OVERLAP = 150  # chars
TOP_K_PDF = 3  # top chunks to display


# =========================
# Utility: PDF Loading & Indexing
# =========================
def load_pdfs(pdf_dir: str) -> Dict[str, str]:
    """
    Read PDFs from a directory and return a dict: {filename: full_text}.
    """
    pdf_texts = {}
    if not os.path.isdir(pdf_dir):
        return pdf_texts

    for fname in os.listdir(pdf_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(pdf_dir, fname)
        try:
            reader = PdfReader(fpath)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            if text.strip():
                pdf_texts[fname] = text
        except Exception as e:
            print(f"Failed to read {fpath}: {e}")
    print("Length:", len(pdf_texts))
    print("Sample:", list(pdf_texts.values())[0][:1000])
    return pdf_texts


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split long text into slightly overlapping chunks for retrieval.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def build_pdf_index(pdf_texts: Dict[str, str]) -> Tuple[List[str], List[str], TfidfVectorizer]:
    """
    Create TF-IDF index over all PDF chunks.
    Returns:
      - chunks: list of chunk strings
      - sources: list of corresponding filenames for chunks
      - vectorizer: fitted TfidfVectorizer
    """
    chunks = []
    sources = []
    for fname, text in pdf_texts.items():
        for ch in chunk_text(text):
            chunks.append(ch)
            sources.append(fname)

    if not chunks:
        # Create an empty vectorizer (to avoid None checks downstream)
        vectorizer = TfidfVectorizer().fit(["placeholder"])
        return [], [], vectorizer

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_df=0.95,
        min_df=1,
        ngram_range=(1, 2)
    )
    # Fit/transform corpus
    vectorizer.fit(chunks)
    return chunks, sources, vectorizer


def retrieve_from_pdfs(
    question: str,
    chunks: List[str],
    sources: List[str],
    vectorizer: TfidfVectorizer,
    top_k: int = TOP_K_PDF
) -> List[Tuple[str, str, float]]:
    """
    Retrieve top-k chunks relevant to the question.
    Returns list of (chunk_text, source_filename, score)
    """
    if not chunks:
        return []

    q_vec = vectorizer.transform([question])
    c_vecs = vectorizer.transform(chunks)
    sims = cosine_similarity(q_vec, c_vecs)[0]
    top_indices = sims.argsort()[::-1][:top_k]
    results = [(chunks[i], sources[i], float(sims[i])) for i in top_indices if sims[i] > 0.05]
    return results


# =========================
# Utility: Intent Recognition for Build Scripts
# =========================
CONFIG_RESULTS_PATTERN = re.compile(
    r"(config(?:uration)?\s+results?.*?\bbuild\b\s*(\d+))",
    flags=re.IGNORECASE
)

FETCH_LOGS_PATTERN = re.compile(
    r"(fetch\s+logs?.*?\bbuild\b\s*(\d+).*\bconfig(?:uration)?\b\s*([A-Za-z0-9_\-]+))",
    flags=re.IGNORECASE
)


def parse_intent(question: str) -> Dict[str, str]:
    """
    Identify if the question requests config results or log fetching.
    Returns dict with keys: intent, build, config
    """
    intent = {"intent": "general", "build": None, "config": None}

    # Configuration results for a build
    m1 = CONFIG_RESULTS_PATTERN.search(question)
    if m1:
        intent["intent"] = "config_results"
        intent["build"] = m1.group(2)
        return intent

    # Fetch logs for build + config
    m2 = FETCH_LOGS_PATTERN.search(question)
    if m2:
        intent["intent"] = "fetch_logs"
        intent["build"] = m2.group(2)
        intent["config"] = m2.group(3)
        return intent

    return intent


# =========================
# Utility: Script Execution
# =========================
def run_script(script_path: str, args: List[str], timeout: int = 60) -> Tuple[bool, str, str]:
    """
    Run an external script with arguments.
    Returns (success, stdout, stderr).
    """
    try:
        proc = subprocess.run(
            [script_path] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        success = proc.returncode == 0
        return success, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return False, "", f"Script not found: {script_path}"
    except subprocess.TimeoutExpired:
        return False, "", f"Script timed out after {timeout}s"


def handle_intent(intent: Dict[str, str]) -> Tuple[bool, str, str]:
    """
    Dispatch to the right script based on intent.
    """
    if intent["intent"] == "config_results" and intent["build"]:
        script = os.path.join(SCRIPTS_DIR, "get_config_results.sh")
        success, out, err = run_script(script, ["--build", intent["build"]])
        return success, out, err

    if intent["intent"] == "fetch_logs" and intent["build"] and intent["config"]:
        script = os.path.join(SCRIPTS_DIR, "fetch_logs.sh")
        success, out, err = run_script(script, ["--build", intent["build"], "--config", intent["config"]])
        return success, out, err

    return False, "", "No matching intent or missing parameters."


# =========================
# Utility: Email Fallback
# =========================
def send_email(to_addr: str, subject: str, body: str) -> Tuple[bool, str]:
    """
    Send an email via SMTP. Returns (success, reference_id).
    """
    reference_id = str(uuid.uuid4())[:8]
    full_subject = f"[Chatbot Escalation] {subject} (Ref: {reference_id})"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = full_subject
    msg["From"] = SMTP_SENDER
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            print("Connecting to SMTP server...")
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
                print("Logged in to SMTP server.")
            server.sendmail(SMTP_SENDER, [to_addr], msg.as_string())
        return True, reference_id
    except Exception as e:
        # Log error and still return a reference for the user to quote
        print(f"Email send failed: {e}")
        return False, reference_id


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Software Release Queries Chatbot", page_icon="💬", layout="centered")

# Terminal-like styling
st.markdown(
    """
    <style>
    .terminal {
        background-color: #0c0c0c;
        color: #cce2ff;
        font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #333;
    }
    .terminal .prompt {
        color: #5cc05c;
    }
    .terminal .system {
        color: #9ec3ff;
    }
    .terminal .error {
        color: #ff6b6b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Software Release Queries Chatbot")
st.caption("Type your question. Type 'exit' to quit. Try: 'What Configs are covered as part of Release?' or 'What is the various Status of a Build?' or 'Get Log for Config1 of Build 1.0.1?'")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_index_built" not in st.session_state:
    st.session_state.pdf_index_built = False
if "pdf_chunks" not in st.session_state:
    st.session_state.pdf_chunks = []
if "pdf_sources" not in st.session_state:
    st.session_state.pdf_sources = []
if "pdf_vectorizer" not in st.session_state:
    st.session_state.pdf_vectorizer = None

# Build PDF index once per session
if not st.session_state.pdf_index_built:
    with st.spinner("Indexing PDFs..."):
        pdf_texts = load_pdfs(PDF_DIR)
        chunks, sources, vectorizer = build_pdf_index(pdf_texts)
        st.session_state.pdf_chunks = chunks
        st.session_state.pdf_sources = sources
        st.session_state.pdf_vectorizer = vectorizer
        st.session_state.pdf_index_built = True

# Render chat history
for m in st.session_state.messages:
    role = m["role"]
    content = m["content"]
    if role == "user":
        st.markdown(f"<div class='terminal'><span class='prompt'>user@chatbot$</span> {content}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='terminal'><span class='system'>bot></span> {content}</div>", unsafe_allow_html=True)

# Input box
user_input = st.chat_input("Your command or question (type 'exit' to quit)")

def format_pdf_results(results: List[Tuple[str, str, float]]) -> str:
    if not results:
        return "No relevant content found in PDFs."
    formatted = []
    for chunk, src, score in results:
        snippet = chunk.strip().replace("\n", " ")
        if len(snippet) > 500:
            snippet = snippet[:500] + " ..."
        formatted.append(f"Source: {src} (score={score:.2f})\nSnippet: {snippet}")
    return "\n\n".join(formatted)

def handle_user_query(query: str) -> str:
    # Exit handling
    if query.strip().lower() == "exit":
        return "Session terminated. Goodbye!"

    # Detect intent for scripts
    intent = parse_intent(query)

    # Try scripts first if intent detected
    if intent["intent"] in ("config_results", "fetch_logs"):
        success, out, err = handle_intent(intent)
        if success and out:
            return f"Script execution successful.\n\nOutput:\n{out}"
        else:
            # If script failed, show error and continue to PDF search
            err_msg = f"Script execution failed: {err or 'Unknown error'}\nFalling back to PDF search..."
            # Proceed to PDF search below with err_msg appended

            # PDF search
            results = retrieve_from_pdfs(
                query,
                st.session_state.pdf_chunks,
                st.session_state.pdf_sources,
                st.session_state.pdf_vectorizer,
            )
            if results:
                return err_msg + "\n\nPDF results:\n" + format_pdf_results(results)
            else:
                # Email escalation
                subject = f"Unanswered query: {query}"
                body = (
                    f"The chatbot could not answer the following query:\n\n{query}\n\n"
                    f"Intent: {intent}\nScript error: {err}\n\n"
                    "Please advise or provide documentation.\n"
                )
                email_ok, ref_id = send_email(MAINTAINER_EMAIL, subject, body)
                status_line = "Email sent to maintainer." if email_ok else "Email sending failed; logged locally."
                return (
                    f"{err_msg}\n\nNo PDF answer.\n{status_line}\n"
                    f"Reference ID: {ref_id}\n"
                    "We will notify you when we have an update."
                )

    # General queries: try PDF search
    results = retrieve_from_pdfs(
        query,
        st.session_state.pdf_chunks,
        st.session_state.pdf_sources,
        st.session_state.pdf_vectorizer,
    )
    if results:
        return "Found relevant information in PDFs:\n\n" + format_pdf_results(results)
    else:
        # Ask a clarifying question once before email, example of recursive prompting
        # In a CLI-chat feel, we can suggest a refinement
        clarification = (
            "I couldn't find a direct answer. Could you clarify your request?\n"
            "- If this is about a build, please include: 'configuration results for build <number>' or 'fetch logs for build <number> on config <name>'.\n"
            "- Or specify keywords that should appear in the PDF.\n"
            "If you prefer, I can escalate this now. Say 'escalate'."
        )
        return clarification

# Process input
if user_input is not None:
    st.session_state.messages.append({"role": "user", "content": user_input})
    bot_reply = handle_user_query(user_input)

    # If user asks to escalate directly
    if user_input.strip().lower() == "escalate":
        subject = "User requested escalation"
        body = (
            "User requested escalation without a resolved answer.\n"
            f"Conversation so far:\n\n" +
            "\n\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        )
        email_ok, ref_id = send_email(MAINTAINER_EMAIL, subject, body)
        status_line = "Email sent to maintainer." if email_ok else "Email sending failed; logged locally."
        bot_reply = f"{status_line}\nReference ID: {ref_id}\nWe will notify you when we have an update."

    st.session_state.messages.append({"role": "bot", "content": bot_reply})
    st.rerun()
