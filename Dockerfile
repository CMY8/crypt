# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip && \
    if [ -f crypto_trading_system/requirements.txt ]; then \
        pip install -r crypto_trading_system/requirements.txt; \
    fi

CMD ["python", "main.py", "paper"]
