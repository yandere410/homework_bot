import logging
import sys
import os
import time
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
        logger.debug('сообщение отправлено')
    except Exception as error:
        raise telegram.TelegramError(f'Ошибка при отправке сообщения:'
                                     f' {error}')


def get_api_answer(timestamp):
    """запрос к api."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, params=params, headers=HEADERS)
    except Exception as error:
        logger.error(f'Ошибка при запросе api: {error}')
        return None
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Статус ответа сервере не {HTTPStatus.OK}',
        )
    return response.json()


def check_response(response):
    """проверка ответа api."""
    if not isinstance(response, dict):
        raise TypeError('неверный формат api')
    if 'homeworks' not in response:
        raise ValueError('отуствуют ожидаемые ключи в ответе api')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'неверный формат api, {homeworks}')
    if not 'homeworks':
        logger.info('нет новых заданий')
    return homeworks


def parse_status(homework):
    """текущий статус работы."""
    if 'status' not in homework or 'homework_name' not in homework:
        raise ValueError(f'ответ api не содержит ключа {homework}')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error('Недокументированный статус домашней работы')
        raise ValueError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсуствует токен, программа приостановлена',
                        exc_info=True
                        )
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
                logger.info(f'Новое сообщение: {message}')
                timestamp = response.get['current_date']
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}', exc_info=True)
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
