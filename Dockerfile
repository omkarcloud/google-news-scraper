FROM chetan1111/botasaurus:chrome-151

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

RUN mkdir app
WORKDIR /app
COPY . /app

EXPOSE 8000

# Every endpoint is plain HTTP. Real Chrome + Xvfb come with the base image
# only for the rare fallback: when Google blocks every plain request, one
# headed Chrome replays it.
CMD ["python", "run.py"]
