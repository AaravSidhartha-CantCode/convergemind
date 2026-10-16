FROM python:3.11-slim

WORKDIR /app

# Dependencies first so code changes do not bust the layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# One container runs both processes: uvicorn bound to loopback for the
# Streamlit front end to call, and Streamlit itself on the public $PORT.
# Two Railway services would also work, but this keeps the judge-facing
# surface to a single URL with no cross-origin configuration.
ENV API_BASE_URL=http://127.0.0.1:8000
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8501

CMD ["sh", "-c", "uvicorn backend.api:app --host 127.0.0.1 --port 8000 & exec streamlit run ui/streamlit_app.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true"]
