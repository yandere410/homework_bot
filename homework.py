import logging
import sys
import os
import time
from http import HTTPStatus

import requests
import telegram
from telegram.error import TelegramError
from dotenv import load_dotenv

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


def check_tokens():
    """проверка токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_error_message(bot, error_message):
    """отправка сообщения об ошибке в тг"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, f'{error_message}')
    except TelegramError as telegram_error:
        logger.error(f'ошбка отправки сообщения об ошибке {telegram_error}')


def send_message(bot, message):
    """отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        raise Exception(f'Ошибка при отправке сообщения:'
                        f' {error}')
    else:
        logger.debug('сообщение отправлено')
        send_error_message(bot, error_message='сообщение отправлено')


def get_api_answer(timestamp):
    """запрос к api."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, params=params, headers=HEADERS)
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(
                f'Статус ответа сервере не {HTTPStatus.OK}',
            )
        try:
            data = response.json()
        except ValueError as error:
            raise ConnectionError('Ошибка при обработке ответа API') from error
        return data
    except requests.exceptions.RequestException as error:
        raise ConnectionError from error


def check_response(response):
    """проверка ответа api."""
    if not isinstance(response, dict):
        raise TypeError('неверный формат API')
    if 'homeworks' not in response:
        raise KeyError('отуствуют ожидаемые ключи в ответе api')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'неверный формат API, {homeworks}')
    if 'current_date' not in response:
        raise KeyError('отсутсвует ключ "current_date')
    return homeworks


def parse_status(homework):
    """текущий статус работы."""
    if 'homework_name' not in homework:
        raise ValueError(f'ответ api не содержит ключа {homework}')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def handle_homework(bot, homework):
    """вспомогательная функция статуса работы"""
    try:
        message = parse_status(homework)
        if message:
            return message
    except Exception as parse_error:
        logger.error(f'ошибка парсинга {parse_error}')
    return None


def handle_response(bot, response):
    """вспомогательная функция обработки запросов"""
    try:
        homeworks = check_response(response)
        if homeworks:
            return handle_homework(bot, homeworks[0])
    except ValueError as api_error:
        logger.error(f'ощибка в запросе API {api_error}')
    return None


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        logger.critical('Отсуствует токен, программа приостановлена',
                        exc_info=True
                        )
        send_error_message(bot, error_message='отсуствует токен')
        raise SystemExit
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            message = handle_response(bot, response)
            if message:
                send_message(bot, message)
                logger.info(f'Новое сообщение: {message}')
            if 'current_date' not in response:
                logger.error('отсутсвует ключ "current_date"')
                send_error_message(bot,
                                   error_message='нет ключа "current_date"')
                timestamp = response.get('current_date')
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}', exc_info=True)
            send_error_message(bot, error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(name)s, %(message)s',
        filename='homework.log'
    )
    logger_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(logger_handler)
    main()
