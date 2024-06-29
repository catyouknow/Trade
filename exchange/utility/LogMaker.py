import sys
from exchange.model import MarketOrder, COST_BASED_ORDER_EXCHANGES, STOCK_EXCHANGES
from exchange.utility import settings
from datetime import datetime, timedelta
import requests
from loguru import logger
from devtools import debug, pformat
import traceback
import os

logger.remove(0)
logger.add(
    "./log/poa.log",
    rotation="1 days",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(
    sys.stderr,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>",
)

try:
    make_webhook_url = "https://hook.eu2.make.com/qcv5rm1s1l4fohqm74qn7gmk2bhkajuv"  # Make.com 웹훅 URL
except Exception as e:
    print("웹훅 URL이 유효하지 않습니다: ")


def get_error(e):
    tb = traceback.extract_tb(e.__traceback__)
    target_folder = os.path.abspath(os.path.dirname(tb[0].filename))
    error_msg = []

    for tb_info in tb:
        error_msg.append(f"File {tb_info.filename}, line {tb_info.lineno}, in {tb_info.name}")
        if "raise error." in tb_info.line:
            continue
        error_msg.append(f"  {tb_info.line}")

    error_msg.append(str(e))

    return "\n".join(error_msg)


def parse_time(utc_timestamp):
    timestamp = utc_timestamp + timedelta(hours=9).seconds
    date = datetime.fromtimestamp(timestamp)
    return date.strftime("%y-%m-%d %H:%M:%S")


def logger_test():
    date = parse_time(datetime.utcnow().timestamp())
    logger.info(date)


def log_message(message="None"):
    if make_webhook_url:
        payload = {
            "content": message
        }
        response = requests.post(make_webhook_url, json=payload)
        if response.status_code != 200:
            logger.error(f"웹훅 호출 실패: {response.status_code} - {response.text}")
    else:
        logger.info(message)
        print(message)



def log_order_message(exchange_name, order_result: dict, order_info: MarketOrder):
    date = parse_time(datetime.utcnow().timestamp())
    if not order_info.is_futures and order_info.is_buy and exchange_name in COST_BASED_ORDER_EXCHANGES:
        f_name = "비용"
        if order_info.amount is not None:
            if exchange_name == "UPBIT":
                amount = str(order_result.get("cost"))
            elif exchange_name == "BITGET":
                amount = str(order_info.amount * order_info.price)
            elif exchange_name == "BYBIT":
                amount = str(order_result.get("info").get("orderQty"))
        elif order_info.percent is not None:
            f_name = "비율"
            amount = f"{order_info.percent}%"

    else:
        f_name = "수량"
        amount = None
        if exchange_name in ("KRX", "NASDAQ", "AMEX", "NYSE"):
            if order_info.amount is not None:
                amount = str(order_info.amount)
            elif order_info.percent is not None:
                f_name = "비율"
                amount = f"{order_info.percent}%"
        elif order_result.get("amount") is None:
            if order_info.amount is not None:
                if exchange_name == "OKX":
                    if order_info.is_futures:
                        f_name = "계약(수량)"
                        amount = f"{order_info.amount // order_info.contract_size}({order_info.contract_size * (order_info.amount // order_info.contract_size)})"
                    else:
                        amount = f"{order_info.amount}"
                else:
                    amount = str(order_info.amount)
            elif order_info.percent is not None:
                if order_info.amount_by_percent is not None:
                    f_name = "비율(수량)" if order_info.is_contract is None else "비율(계약)"
                    amount = f"{order_info.percent}%({order_info.amount_by_percent})"
                else:
                    f_name = "비율"
                    amount = f"{order_info.percent}%"
        elif order_result.get("amount") is not None:
            if order_info.contract_size is not None:
                f_name = "계약"
                if order_result.get("cost") is not None:
                    f_name = "계약(비용)"
                    amount = f"{order_result.get('amount')}({order_result.get('cost'):.2f})"
                else:
                    amount = f"{order_result.get('amount')}"
            else:
                if order_info.amount is not None:
                    f_name = "수량"
                    amount = f"{order_result.get('amount')}"
                elif order_info.percent is not None:
                    f_name = "비율(수량)" if order_info.is_contract is None else "비율(계약)"
                    amount = f"{order_info.percent}%({order_result.get('amount')})"

    symbol = f"{order_info.base}/{order_info.quote+'.P' if order_info.is_crypto and order_info.is_futures else order_info.quote}"

    side = ""
    if order_info.is_futures:
        if order_info.is_entry:
            if order_info.is_buy:
                side = "롱 진입"
            elif order_info.is_sell:
                side = "숏 진입"
        elif order_info.is_close:
            if order_info.is_buy:
                side = "숏 종료"
            elif order_info.is_sell:
                side = "롱 종료"
    else:
        if order_info.is_buy:
            side = "매수"
        elif order_info.is_sell:
            side = "매도"

    if exchange_name in STOCK_EXCHANGES:  # ("KRX", "NASDAQ", "NYSE", "AMEX"):
        content = f"일시\n{date}\n\n거래소\n{exchange_name}\n\n티커\n{order_info.base}\n\n거래유형\n{side}\n\n{amount}"
    else:
        content = f"일시\n{date}\n\n거래소\n{exchange_name}\n\n심볼\n{symbol}\n\n거래유형\n{order_result.get('side')}\n\n{amount}"

    log_message(content)



def log_hedge_message(exchange, base, quote, exchange_amount, upbit_amount, hedge):
    date = parse_time(datetime.utcnow().timestamp())
    hedge_type = "헷지" if hedge == "ON" else "헷지 종료"
    content = (
        f"**헷지**: {base} ==> {exchange}:{exchange_amount} UPBIT:{upbit_amount}\n"
        f"**일시**: {date}\n"
        f"**거래소**: {exchange}-UPBIT\n"
        f"**심볼**: {base}/{quote}-{base}/KRW\n"
        f"**거래유형**: {hedge_type}\n"
        f"**수량**: {exchange}:{exchange_amount} UPBIT:{upbit_amount}"
    )
    log_message(content)


def log_error_message(error, name):
    error_msg = f"[{name} 에러가 발생했습니다]\n{error}"
    logger.error(f"{name} [에러가 발생했습니다]\n{error}")
    log_message(error_msg)


def log_order_error_message(error: str | Exception, order_info: MarketOrder):
    if isinstance(error, Exception):
        error = get_error(error)

    error_msg = f"[주문 오류가 발생했습니다]\n{error}"

    if order_info is not None:
        log_message(error_msg)
        logger.error(f"[주문 오류가 발생했습니다]\n{error}")
    else:
        log_message(error_msg)
        logger.error(f"[오류가 발생했습니다]\n{error}")

def log_validation_error_message(msg):
    logger.error(f"검증 오류가 발생했습니다\n{msg}")
    log_message(msg)


def print_alert_message(order_info: MarketOrder, result="성공"):
    msg = pformat(order_info.dict(exclude_none=True))

    if result == "성공":
        logger.info(f"주문 {result} 웹훅메세지\n{msg}")
    else:
        logger.error(f"주문 {result} 웹훅메세지\n{msg}")


def log_alert_message(order_info: MarketOrder, result="성공"):
    order_info_dict = order_info.dict(exclude_none=True)
    msg = f"[웹훅 alert_message] {order_info.order_name}\n"

    for key, value in order_info_dict.items():
        msg += f"{key}: {value}\n"

    log_message(msg)

    # logger
    print_alert_message(order_info, result)