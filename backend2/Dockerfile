# Build image:
#   docker build -t zenfru-agent-backend2 .
# Run container:
#   docker run -p 8000:8000 zenfru-agent-backend2
# Use official Python image
FROM python:3.11-slim

# Install system updates and security patches
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . ./

# Expose port 
EXPOSE 8000

# Set default command to run your app
CMD ["python", "main.py"]
