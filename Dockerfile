FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
# opencv-python (dependencia de RapidOCR) necesita libGL y glib en la imagen slim.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
# Carga el OCR una vez en la build: falla aquí y no en la primera tarea si falta algo.
RUN python -c "from app.perception import engine; engine()"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
