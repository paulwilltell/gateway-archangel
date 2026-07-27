FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
# --no-access-log is not optional: uvicorn's access log records every
# visitor's IP address. Gateway stores no accounts and no conversations
# precisely so there is no list of who reads or writes here; leaving the
# access log on would rebuild that list in stdout. See docs/THREAT_MODEL.md.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
