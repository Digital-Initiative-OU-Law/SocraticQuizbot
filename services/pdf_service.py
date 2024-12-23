import os
import pdfplumber
import streamlit as st
import re
import concurrent.futures
import threading
import hashlib
from functools import lru_cache
from typing import Dict, List, Tuple
import gc
from services.openai_service import OpenAIService

class PDFService:
    def __init__(self):
        self.readings_folder = 'Readings'
        self.supported_formats = ['.pdf']
        self.extraction_threads = 2
        self.file_cache = {}
        self.summary_cache = {}
        self._cache_lock = threading.Lock()
        self.openai_service = OpenAIService()

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file with memory efficient chunking"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _process_page(self, page) -> str:
        try:
            text = page.extract_text(
                layout=True,
                x_tolerance=3,
                y_tolerance=3
            )
            return text.strip() if text else ""
        except Exception as e:
            print(f"Error processing page: {str(e)}")
            return ""

    def _process_pdf_parallel(self, pdf_path: str) -> str:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                text_chunks = []
                batch_size = 5
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for batch_start in range(0, total_pages, batch_size):
                    batch_end = min(batch_start + batch_size, total_pages)
                    batch_pages = list(range(batch_start, batch_end))
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.extraction_threads) as executor:
                        futures = {
                            executor.submit(self._process_page, pdf.pages[i]): i 
                            for i in batch_pages
                        }
                        
                        for future in concurrent.futures.as_completed(futures):
                            page_num = futures[future]
                            try:
                                text = future.result()
                                if text:
                                    text_chunks.append(text)
                            except Exception as e:
                                st.error(f"Error processing page {page_num + 1}: {str(e)}")
                    
                    progress = min((batch_end) / total_pages, 1.0)
                    progress_bar.progress(progress)
                    status_text.write(f"Processing pages {batch_start + 1}-{batch_end}/{total_pages}")
                    gc.collect()
                
                progress_bar.empty()
                status_text.empty()
                
                return '\n\n'.join(text_chunks)
                
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return ""

    def _generate_summary(self, text: str, filename: str) -> str:
        """Generate a summary of concepts from the text"""
        prompt = f"""Create a concise summary of the key concepts from this document. 
        Focus on the main ideas, theories, and important points that could be used for 
        Socratic questioning. Format the output as a list of concepts, each with a brief explanation.
        Document: {filename}
        Text: {text}"""
        
        return self.openai_service.generate_summary(prompt)

    def extract_summaries(self, folder_path: str) -> Dict[str, str]:
        """Extract and summarize text from all PDFs in the folder"""
        try:
            if not os.path.exists(folder_path):
                st.error(f"Readings folder not found: {folder_path}")
                return {}
                
            pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
            if not pdf_files:
                st.error("No PDF files found in Readings folder")
                return {}
            
            summaries = {}
            for filename in pdf_files:
                file_path = os.path.join(folder_path, filename)
                try:
                    if os.path.getsize(file_path) == 0:
                        st.warning(f"Skipping empty file: {filename}")
                        continue
                    
                    # Check cache for summary
                    file_hash = self._calculate_file_hash(file_path)
                    cache_key = f"summary_{file_hash}"
                    
                    with self._cache_lock:
                        if cache_key in self.summary_cache:
                            summaries[filename] = self.summary_cache[cache_key]
                            st.info(f"Retrieved summary for {filename} from cache")
                            continue
                    
                    # Process PDF and generate summary
                    text = self._process_pdf_parallel(file_path)
                    if text.strip():
                        summary = self._generate_summary(text, filename)
                        if summary:
                            summaries[filename] = summary
                            with self._cache_lock:
                                self.summary_cache[cache_key] = summary
                        else:
                            st.warning(f"Failed to generate summary for {filename}")
                    else:
                        st.warning(f"No text content found in {filename}")
                        
                except Exception as e:
                    st.error(f"Error processing {filename}: {str(e)}")
                    continue
            
            # Combine summaries with document separators
            if not summaries:
                st.error("No summaries could be generated from PDF files")
                return {}
                
            return summaries
            
        except Exception as e:
            st.error(f"Error accessing folder {folder_path}: {str(e)}")
            return {}
