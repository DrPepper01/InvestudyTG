FROM python:3.10-slim

RUN apt-get update && apt-get install -y libpq-dev gcc

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

ENV DJANGO_SETTINGS_MODULE=ProjectTG.settings

COPY . /app/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
