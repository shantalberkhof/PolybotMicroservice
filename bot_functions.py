import boto3
from loguru import logger
from botocore.exceptions import ClientError
import requests
import os
import json

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


def get_secret_value(region_name, secret_name, key_name=None):
    try:
        secret_manager = boto3.client('secretsmanager', region_name)

        response = secret_manager.get_secret_value(SecretId=secret_name)
    except Exception as e:
        logger.exception(f"Retrieval of secret {secret_name} failed. An Unknown {type(e).__name} has occurred.\n{str(e)}")
        return f"Retrieval of secret {secret_name} failed. An Unknown {type(e).__name} has occurred.", 500

    secret_str = response.get("SecretString", "")

    if not secret_str:
        logger.exception(f"Retrieval of secret {secret_name} failed. Secret value is empty")
        return f"Retrieval of secret {secret_name} failed. Secret value is empty", 500

    if key_name:
        # Parse the JSON string to get the actual values
        secret_dict = json.loads(secret_str)

        # Access the specific value you need
        secret_value = secret_dict[key_name]
    else:
        secret_value = secret_str

    logger.info(f"Fetching secret: {secret_name}, succeeded.")
    return secret_value, 200


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
