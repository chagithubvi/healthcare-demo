FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for builds
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 8501

# Run Streamlit
CMD streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0