FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY main.py .
COPY src/ ./src/

# Create directories
RUN mkdir -p reports logs

# Run the report generation
CMD ["python", "main.py"]
