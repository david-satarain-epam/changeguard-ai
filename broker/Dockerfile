# Usa una imagen base oficial de Python.
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor.
WORKDIR /app

# Establece la variable de entorno PYTHONPATH para asegurar que los módulos se encuentren.
# Esto ayuda a resolver las importaciones relativas como 'from services.policy_engine import ...'
ENV PYTHONPATH=/app

# Copia solo el archivo de requerimientos primero para aprovechar el cache de capas de Docker.
COPY requirements.txt .

# Instala las dependencias.
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación del broker al contenedor.
COPY . /app/

# Copia explícitamente los archivos de datos a una ubicación conocida.
COPY data/ /app/data/

# Expone el puerto 8080, que es el estándar que Cloud Run espera.
EXPOSE 8080

# Define el comando por defecto para ejecutar la aplicación cuando el contenedor inicie.
CMD ["python", "server.py"]