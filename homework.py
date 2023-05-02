import os
import sys
import time
import telegram
import requests
import logging

from http import HTTPStatus
from dotenv import load_dotenv
from requests import RequestException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


MESSAGE_NOT_SENT = 'Не удалось отправить сообщение.'
MESSAGE_SENT = 'Отправлено сообщение:'
REQUEST_ERROR_MESSAGE = 'Ошибка при запросе к эндпоинту'
ENDPOINT_UNAVAIBLE = 'Недоступность эндпоинта'
API_RESPONSE_CODE = 'Код ответа API:'
API_NOT_DICTIONARY = 'Ответ API не является словарем.'
ERROR_IN_DICTIONARY = 'Ошибка в получении значений словаря.'
API_NOT_EXPECTED = 'Ответ API не соответствует ожиданиям.'
ABSENT = 'Отсутствует или пустое поле:'
UNKNOWN_STATUS = 'Неизвестный статус:'
NO_ENVIRONMENT_VARIABLE = 'Отсутствует переменная окружения'
NO_NEW_STATUS = 'Новые статусы в ответе отсутствуют'
PROGRAM_FAIL = 'Сбой в работе программы:'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_names = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for token_name, value in token_names.items():
        if value is None:
            logging.error(F'{token_name} not found')
    return all(token_names.values())


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(MESSAGE_SENT.format(message))
    except telegram.TelegramError:
        logger.error(MESSAGE_NOT_SENT)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except RequestException:
        logger.exception(REQUEST_ERROR_MESSAGE({ENDPOINT}))
    if response.status_code != HTTPStatus.OK:
        raise Exception(
            ENDPOINT_UNAVAIBLE({ENDPOINT}),
            API_RESPONSE_CODE.format(response.status_code),
        )
    return response.json()


def check_response(response):
    """Проверка соответсивия полученного ответа."""
    if not isinstance(response, dict):
        raise TypeError(API_NOT_DICTIONARY)
    homeworks = response.get('homeworks')
    current_date = response.get('current_date')
    if (homeworks is None or current_date is None):
        raise KeyError(ERROR_IN_DICTIONARY)
    if not isinstance(homeworks, list):
        raise TypeError(API_NOT_EXPECTED)
    return homeworks


def parse_status(homework):
    """Показывает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError(ABSENT.format(homework_name))
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(UNKNOWN_STATUS.format(homework_status))
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(NO_ENVIRONMENT_VARIABLE)
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug(NO_NEW_STATUS)
            timestamp = response.get('current_date')
        except Exception as error:
            message = PROGRAM_FAIL.format(error)
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
