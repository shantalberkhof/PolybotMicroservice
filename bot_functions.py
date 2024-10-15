import boto3
from loguru import logger
from botocore.exceptions import ClientError
import requests
import os
import json

REGION_NAME = os.environ['REGION_NAME'] # new from terraform


# older func
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


def get_secret_value(region_name, secret_name):
    try:
        secret_manager = boto3.client('secretsmanager', region_name)

        response = secret_manager.get_secret_value(SecretId=secret_name)
    except Exception as e:
        logger.exception(f"Retrieval of secret {secret_name} failed.  Endpoint connection error occurred.\n{str(e)}")
        return f"Retrieval of secret {secret_name} failed. Endpoint connection error occurred.", 500

    secret_str = response.get("SecretString", "")

    if not secret_str:
        logger.exception(f"Retrieval of secret {secret_name} failed. Secret value is empty")
        return f"Retrieval of secret {secret_name} failed. Secret value is empty", 500

    # Ensure the secret is a string (just in case)
    if not isinstance(secret_str, str):
        logger.error(f"Secret value for {secret_name} is not a string: {secret_str}")
        return f"Secret value for {secret_name} is not a string.", 500

    logger.info(f"Fetching secret: {secret_name}, succeeded.")
    return secret_str


def load_telegram_token():
    #secret_name = 'shantal-telegram-bot-token'
    # region_name = 'us-east-2'
    #region_name=REGION_NAME
    secret_name = 'tf-telegram-botToken-us-east-1'
    secrets = get_secret_value(secret_name, REGION_NAME)
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
