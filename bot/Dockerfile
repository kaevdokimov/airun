FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY main.py handlers.py api_client.py keyboards.py states.py middleware.py ./
RUN pip install --no-cache-dir .

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
