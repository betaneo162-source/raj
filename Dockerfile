FROM ubuntu:22.04
RUN apt update && apt install -y gcc python3 python3-pip
COPY raj.c /app/
COPY raj /app/raj
COPY api.py /app/
WORKDIR /app
RUN chmod +x raj
RUN gcc -pthread -O3 -o raj raj.c -lm
RUN pip3 install flask pymongo
CMD ["python3", "api.py"]