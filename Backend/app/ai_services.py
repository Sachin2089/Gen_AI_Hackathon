import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import documentai
from pdf2image import convert_from_bytes
import json
import os
import re
import cv2
import numpy as np
from typing import Dict, List
from sentence_transformers import SentenceTransformer, util

class LegalDocumentProcessor:
    def __init__(self):
       
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        vertexai.init(project=project_id, location="us-central1")
    
        self.doc_ai_client = documentai.DocumentProcessorServiceClient()
        # Use OCR-specialized processor
        self.processor_name = f"projects/{project_id}/locations/us/processors/b26232f7d89f7e08"
        
        # Initialize Gemini model
        self.model = GenerativeModel("gemini-2.5-pro")
        
        # Initialize Sentence Transformer for semantic search
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def extract_text_from_pdf(self, file_content: bytes, mime_type: str = "application/pdf") -> str:
        """Preprocess PDF into images and extract text from each page using Document AI OCR processor"""
        processed_images = self._preprocess_pdf(file_content)
        full_text = ""

        for image_content in processed_images:
            document = documentai.RawDocument(content=image_content, mime_type="image/png")
            request = documentai.ProcessRequest(name=self.processor_name, raw_document=document)
            result = self.doc_ai_client.process_document(request=request)
            full_text += result.document.text + "\n\n"
        
        return full_text

    def _preprocess_pdf(self, file_content: bytes) -> List[bytes]:
        """Convert PDF pages to high-res binarized PNG images"""
        images = convert_from_bytes(file_content, dpi=300)
        processed_images = []
        
        for img in images:
            open_cv_image = np.array(img.convert('RGB'))
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            _, encoded_img = cv2.imencode('.png', binary)
            processed_images.append(encoded_img.tobytes())
        
        return processed_images

    def _extract_clause_references(self, original_text: str, clauses: List[str]) -> Dict[str, List[str]]:
        """Use semantic similarity to find best matching sentences in original text"""
        clause_references = {}
        sentences = [s.strip() for s in original_text.split('.') if len(s.strip()) > 20]
        sentence_embeddings = self.similarity_model.encode(sentences, convert_to_tensor=True)
        
        for i, clause in enumerate(clauses):
            clause_id = f"clause_{i+1}"
            clause_embedding = self.similarity_model.encode(clause, convert_to_tensor=True)
            hits = util.semantic_search(clause_embedding, sentence_embeddings, top_k=2)
            matched_sentences = [sentences[hit['corpus_id']] for hit in hits[0]]
            clause_references[clause_id] = matched_sentences
        
        return clause_references

    def _highlight_text_with_clauses(self, original_text: str, clause_references: Dict[str, List[str]]) -> str:
        highlighted_text = original_text
        
        for clause_id, references in clause_references.items():
            for ref_text in references:
                if ref_text and len(ref_text.strip()) > 20:
                    highlighted_text = highlighted_text.replace(
                        ref_text,
                        f'<span class="highlighted-clause" data-clause-id="{clause_id}" title="Key Clause">{ref_text}</span>'
                    )
        
        return highlighted_text

    async def simplify_legal_document(self, text: str, document_type: str = "contract") -> dict:
        prompt = f"""
        You are a legal expert specializing in making complex legal documents accessible to everyday people.
        
        Document Type: {document_type}
        
        Please analyze this legal document and provide a structured response with the following sections.
        For each section, provide content that can be rendered as HTML:
        
        1. SIMPLIFIED_SUMMARY: A clear, plain-language summary in markdown format with proper paragraphs
        2. KEY_CLAUSES: List the 5 most important clauses. For each clause, provide:
           - title: Short descriptive title
           - explanation: Plain-language explanation
           - importance: Why this clause matters (High/Medium/Low)
           - original_excerpt: The actual text from the document (if identifiable)
        3. RISK_ASSESSMENT: 
           - overall_risk: Number from 1-10
           - risk_factors: List of specific risks with severity levels
        4. IMPORTANT_TERMS: Key legal terms with definitions
        5. ACTION_ITEMS: Specific things the reader should know or do
        
        Make everything conversational and easy to understand. Avoid legal jargon.
        Format your response as valid JSON.
        
        Document text:
        {text}
        """
        
        response = self.model.generate_content(prompt)
        
        try:
            clean_text = response.text.strip()

            if clean_text.startswith("json"):
                clean_text = clean_text.replace("json", "", 1).strip()

            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(json)?", "", clean_text).strip()
                clean_text = re.sub(r"```$", "", clean_text).strip()

            result = json.loads(clean_text)
            formatted_result = self._format_response_with_html(result, text)
            return formatted_result
            
        except json.JSONDecodeError:
            return {
                "SIMPLIFIED_SUMMARY": {response.text},
                "KEY_CLAUSES": [{"title": "Unable to parse", "explanation": "Please review manually", "importance": "Medium"}],
                "RISK_ASSESSMENT": {"overall_risk": 5, "risk_factors": []},
                "IMPORTANT_TERMS": {},
                "ACTION_ITEMS": ["<p>Review document carefully</p>"],
                "highlighted_document": f"<div class='document-text'>{text}</div>"
            }

    def _format_response_with_html(self, result: dict, original_text: str) -> dict:
        summary = result.get("SIMPLIFIED_SUMMARY", "")
        formatted_summary = f"<div class='summary-section'><p>{summary}</p></div>"
        
        clauses = result.get("KEY_CLAUSES", [])
        formatted_clauses = []
        clause_texts = []
        
        for i, clause in enumerate(clauses):
            if isinstance(clause, dict):
                clause_html = f"""
                <div class='clause-item' data-clause-id='clause_{i+1}'>
                    <h4 class='clause-title'>{clause.get('title', f'Clause {i+1}')}</h4>
                    <div class='clause-importance importance-{clause.get('importance', 'medium').lower()}'>
                        Importance: {clause.get('importance', 'Medium')}
                    </div>
                    <p class='clause-explanation'>{clause.get('explanation', '')}</p>
                    {f"<blockquote class='original-text'>{clause.get('original_excerpt', '')}</blockquote>" if clause.get('original_excerpt') else ''}
                </div>
                """
                formatted_clauses.append(clause_html)
                clause_texts.append(clause.get('explanation', ''))
            else:
                clause_html = f"""
                <div class='clause-item' data-clause-id='clause_{i+1}'>
                    <p class='clause-explanation'>{clause}</p>
                </div>
                """
                formatted_clauses.append(clause_html)
                clause_texts.append(str(clause))
        
        risk_data = result.get("RISK_ASSESSMENT", {})
        if isinstance(risk_data, dict):
            risk_html = f"""
            <div class='risk-assessment'>
                <div class='overall-risk risk-level-{risk_data.get('overall_risk', 5)}'>
                    <strong>Overall Risk Score: {risk_data.get('overall_risk', 5)}/10</strong>
                </div>
                <ul class='risk-factors'>
                    {' '.join([f"<li class='risk-item'>{factor}</li>" for factor in risk_data.get('risk_factors', [])])}
                </ul>
            </div>
            """
        else:
            risk_html = f"<div class='risk-assessment'><p>Risk Score: {risk_data}/10</p></div>"
        
        terms = result.get("IMPORTANT_TERMS", {})
        terms_html = "<div class='terms-section'>"
        if isinstance(terms, dict):
            for term, definition in terms.items():
                terms_html += f"""
                <div class='term-item'>
                    <strong class='term-name'>{term}</strong>: 
                    <span class='term-definition'>{definition}</span>
                </div>
                """
        terms_html += "</div>"
        
        actions = result.get("ACTION_ITEMS", [])
        actions_html = "<ul class='action-items'>"
        for action in actions:
            actions_html += f"<li class='action-item'>{action}</li>"
        actions_html += "</ul>"
        
        clause_references = self._extract_clause_references(original_text, clause_texts)
        highlighted_document = self._highlight_text_with_clauses(original_text, clause_references)
        
        return {
            "SIMPLIFIED_SUMMARY": formatted_summary,
            "KEY_CLAUSES": formatted_clauses,
            "RISK_ASSESSMENT": risk_html,
            "IMPORTANT_TERMS": terms_html,
            "ACTION_ITEMS": actions_html,
            "highlighted_document": f"<div class='document-text'>{highlighted_document}</div>",
            "clause_references": clause_references
        }

    async def answer_document_question(self, document_text: str, question: str) -> str:
        prompt = f"""
        Based on this legal document, answer the user's question in simple, clear language.
        Avoid legal jargon and explain things as if talking to a friend.
        Format your response as HTML with proper paragraphs and emphasis where needed.
        
        Document: {document_text[:2000]}...
        
        Question: {question}
        
        Provide your answer in HTML format with <p>, <strong>, <em> tags as needed.
        """
        
        response = self.model.generate_content(prompt)
        return f"<div class='qa-response'>{response.text}</div>"
