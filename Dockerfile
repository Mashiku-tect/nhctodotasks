FROM python:3.12-slim

<<<<<<< HEAD
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
=======
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8000
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222

WORKDIR /app

RUN apt-get update \
<<<<<<< HEAD
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app app

=======
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

<<<<<<< HEAD
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app

USER app
=======
RUN chmod +x /app/entrypoint.sh
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
<<<<<<< HEAD
CMD ["gunicorn", "nhctodo.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
=======
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
