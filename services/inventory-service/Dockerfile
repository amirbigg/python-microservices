FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -i https://mirror.abrha.net/repository/pypi/simple -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["python", "manage.py", "runserver", "0.0.0.0:8003"]
