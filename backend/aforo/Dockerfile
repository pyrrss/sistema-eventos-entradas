FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generar código protobuf
RUN python3 -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. aforo.proto

# puerto 50051 es convención para gRPC
EXPOSE 50051

CMD ["python", "main.py"]
