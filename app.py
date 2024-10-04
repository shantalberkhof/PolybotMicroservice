import flask
from flask import request
import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from bot import Bot
from bot import ObjectDetectionBot
import logging
import json
from bot_functions import get_secret, load_telegram_token

app = flask.Flask(__name__)

# from the dockerfile
REGION_NAME = os.environ['REGION_NAME'] # new from terraform
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE'] # new from terraform
# SECRET_ID = os.environ['SECRET_ID'] # new from terraform
TELEGRAM_APP_URL = os.getenv('TELEGRAM_APP_URL')
print(f"telegram app url: {TELEGRAM_APP_URL}")

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(DYNAMODB_TABLE)
# table = dynamodb.Table('shantal-dynamoDB-aws')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Get secret of public key (the certificate to use HTTPS in Telegram)
#public_key_value = get_secret("shantal-YOURPUBLICpem", REGION_NAME)
#print(f"Retrieved Public Key Value: {public_key_value}")

# TODO load TELEGRAM_TOKEN value from Secret Manager

# way 2
#secretsmanager = boto3.client('secretsmanager', region_name=REGION_NAME)
#response = secretsmanager.get_secret_value(SecretId=SECRET_ID)
#secret = response['SecretString']
TELEGRAM_TOKEN = load_telegram_token()
if TELEGRAM_TOKEN:
    print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
    bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL)

# way 2
# TELEGRAM_TOKEN = load_telegram_token()
# if TELEGRAM_TOKEN:
#     print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
#     bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL, public_key_value)


# Health checks on ALB
@app.route('/', methods=['GET'])
def index():
    return 'Ok'


@app.route(f'/{TELEGRAM_TOKEN}/', methods=['POST'])
def webhook():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'


@app.route(f'/results', methods=['GET'])
def results():
    prediction_id = request.args.get('predictionId')
    if not prediction_id:
        return 'Missing predictionId', 400

    # TODO use the prediction_id to retrieve results from DynamoDB and send to the end-user
    logger.info(f'Received request for predictionId: {prediction_id}')

    try:
        response = table.get_item(Key={'prediction_id': prediction_id})

        item = response['Item']
        chat_id = item.get('chat_id') # done
        labels = item.get('labels') # done

        # Format the results for sending via Telegram
        text_results = "\n".join([f"Class: {label['class']}, Coordinates: ({label['cx']}, {label['cy']}), Size: ({label['width']}, {label['height']})" for label in labels])

        # Send the message via Telegram
        bot.send_text(chat_id, text_results)

        logger.info(f'Results for predictionId {prediction_id} successfully sent to chat_id {chat_id}')
        return 'Results sent', 200

    except Exception as e:
        logger.error(f'An error occurred while processing predictionId {prediction_id}: {str(e)}')
        return 'Internal server error', 500


@app.route(f'/loadTest/', methods=['POST'])
def load_test():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL)
        logger.info(f'The current region is {REGION_NAME}')
        # Previous way with the public key (the certificate to use HTTPS in Telegram)
        #bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL, public_key_value)
        app.run(host='0.0.0.0', port=8443)
    else:
        logger.error("Application could not start due to missing TELEGRAM_TOKEN.")