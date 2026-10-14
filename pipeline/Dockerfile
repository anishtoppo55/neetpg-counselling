FROM python:3.12.7-slim

# poppler-utils provides pdftotext, used to read word coordinates from the MCC PDFs
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

# run as an unprivileged user
RUN useradd --create-home --uid 1000 pipeline
USER pipeline

ENTRYPOINT ["python", "-m", "neetpg_pipeline"]
CMD ["--help"]
