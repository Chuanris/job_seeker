FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
COPY jobbot ./jobbot
COPY demo ./demo
COPY config.json ./config.json
CMD ["python", "-m", "jobbot"]
