FROM python:3.11-slim
WORKDIR /work

# Split pip installs to prevent OOM (StartOS builder has limited RAM)
RUN pip install --no-cache-dir streamlit>=1.32.0
RUN pip install --no-cache-dir openai>=1.14.0 requests>=2.31.0
RUN pip install --no-cache-dir pandas>=2.0.0 plotly>=5.18.0
RUN pip install --no-cache-dir python-dateutil pytz

# Copy all repo files
COPY . .

CMD ["/bin/bash", "start.sh"]
