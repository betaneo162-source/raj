FROM ubuntu:22.04

# Update and install dependencies
RUN apt update && apt install -y \
    gcc \
    python3 \
    python3-pip \
    libc6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy source files
COPY raj.c /app/
COPY api.py /app/
COPY requirements.txt /app/

# Compile raj binary
RUN gcc -pthread -O3 -o raj raj.c -lm

# Make binary executable
RUN chmod +x raj

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8080

# Run the API
CMD ["python3", "api.py"]
