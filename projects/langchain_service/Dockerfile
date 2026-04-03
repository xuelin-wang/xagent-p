FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

COPY pyproject.toml README.md /app/
COPY components /app/components
COPY bases /app/bases
COPY development /app/development

RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["xagent-langchain-api"]
