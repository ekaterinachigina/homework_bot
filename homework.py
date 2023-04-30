import os
import sys
import time
import telegram
import requests
import logging

from http import HTTPStatus
from dotenv import load_dotenv
from requests import RequestException
from exceptions import TelegramError

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: {message}')
    except telegram.TelegramError:
        raise TelegramError('Не удалось отправить сообщение.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        status = response.status_code
        if status != HTTPStatus.OK:
            raise AssertionError(
                f'Недоступность эндпоинта {ENDPOINT}. Код ответа API: {status}'
            )
        try:
            return response.json()
        except ValueError:
            ValueError('Ошибка преобразования к типам данных Python')
    except RequestException:
        logger.exception(f'ошибка при запросе к эндпоинту {ENDPOINT}.')


def check_response(response):
    """Проверка соответсивия полученного ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')
    homeworks = response.get('homeworks')
    current_date = response.get('current_date')
    if (homeworks is None or current_date is None):
        raise KeyError('Ошибка в получении значений словаря.')
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не соответствует ожиданиям.')
    return homeworks


def parse_status(homework):
    """Показывает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError(f'Отсутствует или пустое поле: {homework_name}')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует переменная окружения')
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
                logger.debug('новые статусы в ответе отсутствуют')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
