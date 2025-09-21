from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app import models
from app.ai_services import LegalDocumentProcessor
import json
from typing import Optional
import os 

app = FastAPI(title="Legal Document Simplifier API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
models.Base.metadata.create_all(bind=models.engine)

# Initialize AI processor
ai_processor = LegalDocumentProcessor()

SAVE_DIR = "extracted_texts"
os.makedirs(SAVE_DIR, exist_ok=True)

def convert_sets_to_lists(obj):
    """Recursively convert sets to lists for JSON serialization"""
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {key: convert_sets_to_lists(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets_to_lists(item) for item in obj]
    return obj


@app.post("/upload-document/")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = "contract",
    db: Session = Depends(models.get_db)
):
    """Upload and process legal document with debug prints"""
    
    print("==== Upload request received ====")
    print("Filename:", file.filename)
    print("Content type:", file.content_type)
    print("Document type:", document_type)

    if not file.filename.endswith(('.pdf', '.txt', '.docx')):
        print("Unsupported file type detected!")
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    try:
        # Read file content
        file_content = await file.read()
        print(f"Read {len(file_content)} bytes from file")


        if file.filename.endswith('.pdf'):
            print("Processing as PDF...")
            extracted_text = await ai_processor.extract_text_from_pdf(
                file_content, "application/pdf"
            )
        else:
            print("Processing as TXT/DOCX...")
            extracted_text = file_content.decode('utf-8', errors='ignore')
            print(f"Extracted text length: {len(extracted_text)} characters")
        
        # Save extracted text to a file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = file.filename.replace(" ", "_").rsplit(".", 1)[0]
        save_path = os.path.join(SAVE_DIR, f"{safe_name}_{timestamp}.txt")
        print("Saving extracted text to:", save_path)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        # Process with AI
        print("Sending text to AI processor...")
        simplified_result = await ai_processor.simplify_legal_document(
            extracted_text, document_type
        )
        print("AI processing complete")
        
        simplified_result_clean = convert_sets_to_lists(simplified_result)

        # Save to database
        db_document = models.Document(
            filename=file.filename,
            original_text=extracted_text,
            simplified_text=json.dumps(simplified_result_clean),
            risk_score=simplified_result.get("RISK_ASSESSMENT", 5),
            key_clauses=json.dumps(simplified_result.get("KEY_CLAUSES", [])),
            processing_status="completed"
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        print("Document saved to DB with ID:", db_document.id)
        
        return {
            "document_id": db_document.id,
            "filename": file.filename,
            "simplified_result": simplified_result,
            "risk_score": db_document.risk_score
        }

    except Exception as e:
        print("Error during upload:", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")



@app.get("/document/{document_id}")
async def get_document(document_id: int, db: Session = Depends(models.get_db)):
    """Get processed document by ID"""
    
    document = db.query(models.Document).filter(
        models.Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "filename": document.filename,
        "original_text": document.original_text,
        "simplified_result": json.loads(document.simplified_text),
        "risk_score": document.risk_score,
        "upload_timestamp": document.upload_timestamp
    }

@app.post("/ask-question/")
async def ask_question(
    document_id: int,
    question: str,
    db: Session = Depends(models.get_db)
):
    """Ask a question about a specific document"""
    print("document_id and question", document_id, question)
    
    document = db.query(models.Document).filter(
        models.Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    answer = await ai_processor.answer_document_question(
        document.original_text, question
    )
    
    return {"question": question, "answer": answer}


