#FROM python:3.10
#WORKDIR /app
#COPY . /app/
#RUN pip install -r requirements.txt
#CMD ["python", "bot.py"]

# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed by some packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy rest of the project files
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
