FROM python:3.10-alpine
WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY polybot .

# Previous Telefram App URL
#ENV TELEGRAM_APP_URL=https://shantal-aws-alb-1835467939.us-east-2.elb.amazonaws.com

#ENV TELEGRAM_APP_URL=https://shantalberkhof-polybot-us-east-1.int-devops.click:443
ENV TELEGRAM_APP_URL=https://shantalberkhof-polybot-us-east-1.int-devops.click
RUN pip install boto3 telebot loguru

CMD ["python3", "app.py"]
