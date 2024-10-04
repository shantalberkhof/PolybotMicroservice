import boto3
from loguru import logger
from botocore.exceptions import ClientError
import requests
import os

REGION_NAME = os.environ['REGION_NAME'] # new from terraform

def get_secret(secret_name, region_name):

    # Create a Secrets Manager client
    #session = boto3.session.Session()
    #client = session.client(service_name='secretsmanager', region_name=region_name)
    client = boto3.client('secretsmanager', region_name=REGION_NAME)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # Handle the error
        raise e

    # Decrypts secret using the associated KMS CMK
    secret = get_secret_value_response['SecretString']

    # Since the secret is a plain certificate string, return it as is
    return secret


def load_telegram_token():
    #secret_name = 'shantal-telegram-bot-token'
    # region_name = 'us-east-2'
    #region_name=REGION_NAME
    secret_name = 'tf-telegram-botToken-us-east-1'
    secrets = get_secret(secret_name, REGION_NAME)
    if secrets is None:
        logger.error("Unable to retrieve secrets. Exiting.")
        return None
    return secrets

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{load_telegram_token()}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    response = requests.post(url, json=payload)
    return response.json()
