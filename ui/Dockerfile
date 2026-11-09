FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit==1.40.* requests pandas
COPY app.py .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--browser.gatherUsageStats=false"]
