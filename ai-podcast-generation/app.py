import streamlit as st
import os
import tempfile
import time
import logging
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Internal Imports (Ensure these paths match your folder structure)
try:
    from src.podcast.script_generator import PodcastScriptGenerator
    from src.podcast.text_to_speech import PodcastTTSGenerator
    from src.web_scraping.web_scraper import WebScraper
except ImportError as e:
    st.error(f"Missing internal modules: {e}. Check your src/ directory structure.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- UI CONFIGURATION ---
st.set_page_config(
    page_title="Podsite - AI Podcast Generator",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 24px; font-weight: 600; color: #ffffff; margin-bottom: 20px; }
    .source-item { background: #2d3748; border-radius: 8px; padding: 12px; margin: 8px 0; border-left: 3px solid #4299e1; }
    .source-title { font-weight: 600; color: #ffffff; margin-bottom: 4px; }
    .source-meta { font-size: 12px; color: #a0aec0; }
    .script-segment { background: #1a202c; border-radius: 8px; padding: 16px; margin: 12px 0; }
    .speaker-1 { border-left: 3px solid #ec4899; }
    .speaker-2 { border-left: 3px solid #10b981; }
    .stButton > button { background: #4299e1; color: white; border-radius: 6px; width: 100%; }
    .source-count { background: #4a5568; color: #ffffff; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: 600; display: inline-block; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
def init_session_state():
    if 'sources' not in st.session_state:
        st.session_state.sources = []
    if 'script_generator' not in st.session_state:
        st.session_state.script_generator = None
    if 'tts_generator' not in st.session_state:
        st.session_state.tts_generator = None
    if 'web_scraper' not in st.session_state:
        st.session_state.web_scraper = None
    if 'firecrawl_key' not in st.session_state:
        st.session_state.firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
    if 'openai_key' not in st.session_state:
        st.session_state.openai_key = os.getenv("OPENAI_API_KEY", "")

# --- COMPONENT INITIALIZERS ---
def initialize_logic():
    """Initializes generators based on available keys."""
    if st.session_state.openai_key:
        try:
            if not st.session_state.script_generator:
                st.session_state.script_generator = PodcastScriptGenerator(st.session_state.openai_key)
            
            if not st.session_state.tts_generator:
                try:
                    st.session_state.tts_generator = PodcastTTSGenerator()
                except Exception as e:
                    logger.warning(f"TTS offline: {e}")
            
            # Initialize Scraper if key exists
            if st.session_state.firecrawl_key and not st.session_state.web_scraper:
                st.session_state.web_scraper = WebScraper(st.session_state.firecrawl_key)
                
            return True
        except Exception as e:
            st.error(f"Initialization Failed: {e}")
    return False

# --- CORE FUNCTIONS ---
def add_url_source(url: str):
    if not st.session_state.web_scraper:
        st.error("Please provide a Firecrawl API key in Settings.")
        return

    with st.spinner(f"Scraping {url}..."):
        try:
            result = st.session_state.web_scraper.scrape_url(url)
            if result.get('success'):
                source_info = {
                    'name': result.get('title', 'Untitled Webpage'),
                    'url': url,
                    'type': 'Website',
                    'content': result.get('content', ''),
                    'word_count': result.get('word_count', 0),
                    'added_at': time.strftime("%Y-%m-%d %H:%M")
                }
                st.session_state.sources.append(source_info)
                st.success("✅ Website added!")
            else:
                st.error(f"Scrape failed: {result.get('error')}")
        except Exception as e:
            st.error(f"Scraping Error: {e}")

def add_text_source(text_content: str, source_name: str):
    source_info = {
        'name': source_name if source_name else f"Text {time.strftime('%H:%M')}",
        'url': None,
        'type': 'Text',
        'content': text_content,
        'word_count': len(text_content.split()),
        'added_at': time.strftime("%Y-%m-%d %H:%M")
    }
    st.session_state.sources.append(source_info)
    st.success("✅ Text source added!")

def generate_podcast_flow(source_name, style, length):
    source = next((s for s in st.session_state.sources if s['name'] == source_name), None)
    if not source: return

    try:
        # 1. Script Generation
        with st.spinner("✍️ Writing Script..."):
            script = st.session_state.script_generator.generate_script_from_text(
                text_content=source['content'],
                source_name=source['name'],
                podcast_style=style.lower(),
                target_duration=length
            )

        # 2. Audio Generation
        if st.session_state.tts_generator:
            with st.spinner("🎵 Rendering Audio... (This takes a moment)"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    audio_files = st.session_state.tts_generator.generate_podcast_audio(
                        podcast_script=script,
                        output_dir=tmp_dir,
                        combine_audio=True
                    )
                    
                    # Display Audio
                    full_audio = next((f for f in audio_files if "complete" in f), None)
                    if full_audio:
                        st.audio(full_audio)
                        with open(full_audio, "rb") as f:
                            st.download_button("📥 Download Podcast", f.read(), "podcast.wav", "audio/wav")
        
        # 3. Show Script
        with st.expander("📖 View Script", expanded=True):
            for line in script.script:
                speaker, text = list(line.items())[0]
                cls = "speaker-1" if "1" in speaker else "speaker-2"
                icon = "👩" if "1" in speaker else "👨"
                st.markdown(f'<div class="script-segment {cls}"><b>{icon} {speaker}:</b> {text}</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Generation Failed: {e}")

# --- SIDEBAR ---
def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="main-header">⚙️ Configuration</div>', unsafe_allow_html=True)
        
        # API Keys
        st.session_state.openai_key = st.text_input("OpenAI Key", value=st.session_state.openai_key, type="password")
        st.session_state.firecrawl_key = st.text_input("Firecrawl Key", value=st.session_state.firecrawl_key, type="password")
        
        if st.button("Update Keys"):
            st.session_state.script_generator = None # Force re-init
            st.rerun()

        st.markdown("---")
        st.markdown("#### 🌐 Quick Add URL")
        url = st.text_input("URL", placeholder="https://...")
        if st.button("Scrape Site") and url:
            add_url_source(url)
            st.rerun()

        st.markdown("---")
        st.markdown(f"#### 📚 Library ({len(st.session_state.sources)})")
        for i, src in enumerate(st.session_state.sources):
            col_a, col_b = st.columns([4, 1])
            col_a.caption(f"{src['type']}: {src['name'][:20]}...")
            if col_b.button("🗑️", key=f"del_{i}"):
                st.session_state.sources.pop(i)
                st.rerun()

# --- MAIN APP ---
def main():
    init_session_state()
    render_sidebar()

    st.markdown('<h1 style="text-align: center;">🎙️ Podsite</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #a0aec0;">Turn any content into a podcast episode</p>', unsafe_allow_html=True)

    if not initialize_logic():
        st.info("👋 Welcome! Please enter your **OpenAI API Key** in the sidebar to get started.")
        return

    tab_text, tab_studio = st.tabs(["📝 Add Content", "🎧 Studio"])

    with tab_text:
        col_name, col_btn = st.columns([3,1])
        name = col_name.text_input("Source Title")
        txt = st.text_area("Paste Content", height=300)
        if st.button("Add to Library") and txt:
            add_text_source(txt, name)

    with tab_studio:
        if not st.session_state.sources:
            st.warning("Your library is empty. Add text or a URL first.")
        else:
            sel_source = st.selectbox("Choose Source", [s['name'] for s in st.session_state.sources])
            c1, c2 = st.columns(2)
            style = c1.selectbox("Tone", ["Conversational", "Educational", "Dramatic"])
            length = c2.selectbox("Target Length", ["5 mins", "10 mins", "15 mins"])
            
            if st.button("🎙️ Start Producing"):
                generate_podcast_flow(sel_source, style, length)

if __name__ == "__main__":
    main()
