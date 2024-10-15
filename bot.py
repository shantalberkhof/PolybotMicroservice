import telebot
from loguru import logger
import os
from telebot.types import InputFile
# added:
import boto3
import json
import uuid
import time
from telebot.apihelper import ApiTelegramException
# from app import REGION_NAME  # Import REGION_NAME from app.py
import concurrent.futures
REGION_NAME = os.environ['REGION_NAME']  # Access the environment variable directly in bot.py
BUCKET_NAME = os.environ['BUCKET_NAME']
TELEGRAM_APP_URL = os.environ['TELEGRAM_APP_URL']
SQS_QUEUE_NAME= os.environ['SQS_QUEUE_NAME']

class Bot:

    def __init__(self, token, telegram_chat_url, publickey): # passed before publickey too.
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)
        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)
        retries = 4
        retry_delay = 1  # initial delay in seconds

        # for attempt in range(retries):
        #     try:
        #         # sets the webhook URL
        #         self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60) # option 2 - cert manager
        #         logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')
        #         break
        #     except ApiTelegramException as e:
        #         if e.error_code == 429:
        #             retry_after = int(e.result_json.get('parameters', {}).get('retry_after', retry_delay))
        #             logger.warning(f'Too Many Requests. Retrying after {retry_after} seconds...')
        #             time.sleep(retry_after)
        #             retry_delay *= 2  # Exponential backoff
        #         else:
        #             logger.error(f"Failed to set webhook: {e}")
        #             raise e  # Re-raise the exception for non-429 errors
        # else:
        #     logger.error("Failed to set webhook after retries")


        retries = 4
        for _ in range(retries):
            try:
                self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}:443/{token}/', certificate=publickey,
                                                     timeout=60)
                logger.info(f'Telegram Bot Information\n{self.telegram_bot_client.get_me()}')
                break  # Break out of the retry loop if successful
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 429:  # Too Many Requests error
                    retry_after = int(e.result_json.get('parameters', {}).get('retry_after', 1))
                    logger.warning(f'Too Many Requests. Retrying after {retry_after} seconds...')
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"Failed to set webhook: {e}")
                    raise e  # Re-raise the exception if it's not a 429 error
        else:
            logger.error("Failed to set webhook after retries")



    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}_{int(time.time())}.jpg"
        file_info.file_path = os.path.join(folder_name, unique_filename)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path

    def send_photo(self, chat_id, img_path, caption=None):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path),
            caption=caption
        )

    def handle_message(self, msg):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {msg}')
        self.send_text(msg['chat']['id'], f'Your original message: {msg["text"]}')


class ObjectDetectionBot(Bot):
    def __init__(self, token, url, publickey):
        super().__init__(token, url, publickey)
        self.s3_client = boto3.client('s3', region_name=REGION_NAME)
        self.sqs_client = boto3.client('sqs', region_name=REGION_NAME)
        self.in_hdl_mes = 0

    def handle_message(self, msg):
        logger.info(f'------------ > Incoming message from telegram: {msg}')
        if self.in_hdl_mes == 0:
            self.in_hdl_mes = 1
            if self.is_current_msg_photo(msg):
                logger.info(f'------------ > THE MESSAGE IS IMAGE <------------')
                self.process_image(msg)  # Goes to function process_image
            self.in_hdl_mes = 0

    def process_image(self, msg):

        count = 1
        if msg.get('caption', '').lower() == "test":
            logger.info(f'Caption is test.')
            count = 3 # Specify how many times to send the same image <---------------------
            logger.info(f'Received "test" command. Sending {count} photos.')

        self.send_multiple_photos(msg, count)

    def send_multiple_photos(self, msg, count):
        chat_id = msg['chat']['id']
        logger.info(f'^^^^ Sending {count} photos ^^^^')
        logger.info(f'^^^^ chat ID: {chat_id} ^^^^')

        # TODO send message to the Telegram end-user (e.g. Your image is being processed. Please wait...)
        if count > 1:
            self.send_text(chat_id, f'Your {count} images are being processed. Please wait...')
        if count == 1:
            self.send_text(chat_id, f'Your {count} image is being processed. Please wait...')

        # i = 0
        for i in range(count):

            try:
                path = self.download_user_photo(msg)  # The unique file name is generated here
                # logger.info(f'------------ > LOCAL PATH NUMBER {i + 1}: {path} <------------')  # LOCAL PATH /PHOTOS

                if not os.path.exists(path):
                    logger.error(f"Image path {path} doesn't exist or is invalid")
                    self.send_text(chat_id, "Image path doesn't exist. Please try again later.")
                    return

                # TODO upload the photo to S3
                # bucket_name = 'shantal-awsproject'
                file_name = os.path.basename(path)

                caption = f"Test image {i + 1}/{count}"
                self.send_photo(chat_id, path, caption=caption)
                logger.info(f"Sent image {path} to chat ID: {chat_id} with caption: {caption}")

                time.sleep(1)  # Add a delay to avoid hitting Telegram rate limits

                # Upload to S3 here for each iteration
                object_key = f'data/Image_number_{i + 1}_{file_name}'  # name and the path (key) to store the image on s3
                try:
                    self.s3_client.upload_file(path, BUCKET_NAME, object_key)
                    logger.info(f'{file_name} {i + 1}/{count} was uploaded to S3 successfully')
                except Exception as e:
                    logger.error(f'Failed to upload {file_name} to S3: {e}')

            except Exception as e:
                logger.error(f"Failed to send image {path}. Error: {e}")


            # TODO send a job to the SQS queue
            # The job message contains information regarding the image to be processed, as well as the Telegram chat_id
            #queue_url = 'https://sqs.us-east-2.amazonaws.com/019273956931/shantal-queue-aws'
            queue_url = SQS_QUEUE_NAME
            chat_id = msg['chat']['id']
            message_body = {
                'bucket_name': BUCKET_NAME,
                'object_key': object_key,
                'file_name': file_name,
                'chat_id': msg['chat']['id']  # Added chat_id to the message body
            }
            logger.debug(f"===========> Sending message to SQS:")
            logger.debug(f"{message_body}")

            try:
                response = self.sqs_client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(message_body)
                )

            except Exception as e:
                logger.error(f'Failed to send message to SQS: {e}')
                response = "Failed to process your image. Please try again later."
                self.send_text(msg['chat']['id'], response)
                return

            logger.info(f'===========> Sent message to SQS: {response.get("MessageId")}')
            logger.info(f'=========== > < ===========')
            time.sleep(8)  # Add a delay to avoid hitting Telegram rate limits