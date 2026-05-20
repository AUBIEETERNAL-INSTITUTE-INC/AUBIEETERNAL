FROM python:3.11-slim
WORKDIR /work

# Install git + system deps
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages — split to avoid OOM
RUN pip install --no-cache-dir streamlit
RUN pip install --no-cache-dir openai requests
RUN pip install --no-cache-dir pandas plotly
RUN pip install --no-cache-dir numpy

# Copy repo files into image as fallback
COPY . .

CMD ["/bin/bash", "start.sh"]
