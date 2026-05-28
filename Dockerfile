FROM python:3.11-slim
WORKDIR /work

# Split pip installs to prevent OOM during build
RUN pip install --no-cache-dir streamlit>=1.32.0
RUN pip install --no-cache-dir openai>=1.14.0 requests>=2.31.0
RUN pip install --no-cache-dir pandas>=2.0.0 plotly>=5.18.0
RUN pip install --no-cache-dir python-dateutil pytz
# API server for browser extension
RUN pip install --no-cache-dir fastapi uvicorn

COPY . .
CMD ["/bin/bash", "start.sh"]
