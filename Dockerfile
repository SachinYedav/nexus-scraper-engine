# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements file first for caching
COPY requirements.txt .

# Install python libraries
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its Chromium browser dependencies automatically
RUN playwright install --with-deps chromium

# Copy all the rest of the project files to the container
COPY . .

# Expose port 7860 (Default for Hugging Face Spaces)
EXPOSE 7860

# Run the FastAPI app on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]