FROM python:3.13-slim

WORKDIR /code

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy PyxLSTM submodule
COPY submodules/PyxLSTM /code/PyxLSTM

RUN pip install -r /code/PyxLSTM/requirements.txt

RUN pip install /code/PyxLSTM

# Copy application code
COPY . /code

# Create models directory
RUN mkdir -p /code/models

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
