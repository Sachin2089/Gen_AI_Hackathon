# ---------------------------
# Dockerfile for Streamlit Frontend
# ---------------------------

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (make sure you have frontend/requirements.txt)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all frontend code
COPY . .

# Streamlit settings
ENV STREAMLIT_PORT=8501
ENV STREAMLIT_HOST=0.0.0.0

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app (replace app.py with your filename)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
