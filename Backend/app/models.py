from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSON  # ✅ Add this for JSON support
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv()

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    original_text = Column(Text)
    simplified_text = Column(Text)
    risk_score = Column(JSON)         # ✅ Changed from Float to JSON
    key_clauses = Column(JSON)        # ✅ Changed from Text to JSON
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="pending")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
