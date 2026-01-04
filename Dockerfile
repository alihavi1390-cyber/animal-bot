FROM python:3.11-slim  # تغییر به 3.11 برای سازگاری بهتر

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
