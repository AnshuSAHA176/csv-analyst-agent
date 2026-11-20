FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scipy \
    duckdb

RUN useradd --create-home --uid 10001 runner

WORKDIR /workspace

COPY run_code.py /workspace/run_code.py

USER 10001:10001

CMD ["python", "-I", "/workspace/run_code.py"]