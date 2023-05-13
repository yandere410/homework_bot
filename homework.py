import logging
import sys
import os
import time
import json
from http import HTTPStatus

import requests
import telegram
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


def send_message(bot, message):
    """отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        logger.error(f'ошибка отправки сообщения {error}')
    else:
        logger.debug('сообщение отправлено')


def get_api_answer(timestamp):
    """запрос к api."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, params=params, headers=HEADERS)
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(
                f'Статус ответа сервере не {HTTPStatus.OK}',
            )
        return response.json()
    except json.decoder.JSONDecodeError as error:
        raise json.JSONDecodeError(
            f'Ошибка при разборе json {error.msg}',
            error.doc, error.pos) from error
    except requests.exceptions.RequestException as error:
        raise ConnectionError(f'ошибка запроса к API {error}') from error


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
        return homeworks
    return homeworks


def parse_status(homework):
    """текущий статус работы."""
    if 'homework_name' not in homework:
        raise KeyError(f'ответ api не содержит ключа {homework}')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        logger.critical(
            'Отсуствует токен, программа приостановлена',
            exc_info=True)
        raise SystemExit('критическая ошибка программа завершена')
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message:
                    send_message(bot, message)
            timestamp = response.get('current_date')
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}', exc_info=True)
            send_message(
                bot,
                message=f'Сбой в работе программы: {error}')
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
