FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Remove any existing tokens (user should mount their own or use web auth)
RUN rm -f token.json

# Expose port
EXPOSE 8766

# Run the app
CMD ["python", "main.py"]
