import os
import time
from notifiers.logging import NotificationHandler
from seleniumbase import SB
from loguru import logger
from locator import LocatorAvito


class AvitoParse:
    """
    Парсинг товаров на avito.ru
    url - начальный url
    keysword_list- список ключевых слов
    count - сколько проверять страниц
    """

    def __init__(self,
                 url: str,
                 keysword_list: list,
                 count: int = 10,
                 max_price: int = 0,
                 min_price: int = 0,

                 ):
        self.url = url
        self.keys_word = keysword_list
        self.count = count
        self.max_price = int(max_price)
        self.min_price = int(min_price)



    def __get_url(self):
        self.driver.open(self.url)
        self.driver.open_new_window() # сразу открываем и вторую вкладку
        self.driver.switch_to_window(window=0)

    def __paginator(self):
        """Кнопка далее"""
        logger.info('Страница успешно загружена. Просматриваю объявления')
        while self.count > 0:
            self.__parse_page()
            """Проверяем есть ли кнопка далее"""
            if self.driver.find_elements(LocatorAvito.NEXT_BTN[1], by="css selector"):
                self.driver.find_element(LocatorAvito.NEXT_BTN[1], by="css selector").click()
                self.count -= 1
                logger.debug("Следующая страница")
            else:
                logger.info("Нет кнопки дальше")
                break

    @logger.catch
    def __parse_page(self):
        """Парсит открытую страницу"""

        """Ограничение количества просмотренных объявлений"""
        if os.path.isfile('viewed.txt'):
            with open('viewed.txt', 'r') as file:
                self.viewed_list = list(map(str.rstrip, file.readlines()))
                if len(self.viewed_list) > 5000:
                    self.viewed_list = self.viewed_list[-900:]
        else:
            with open('viewed.txt', 'w') as file:
                self.viewed_list = []

        titles = self.driver.find_elements(LocatorAvito.TITLES[1], by="css selector")
        self.driver.save_screenshot("1.png")
        for title in titles:
            self.driver.save_screenshot("1.png")
            name = title.find_element(*LocatorAvito.NAME).text

            if title.find_elements(*LocatorAvito.DESCRIPTIONS):
                description = title.find_element(*LocatorAvito.DESCRIPTIONS).text
            else:
                description = ''

            url = title.find_element(*LocatorAvito.URL).get_attribute("href")
            price = title.find_element(*LocatorAvito.PRICE).get_attribute("content")
            ads_id = title.get_attribute("data-item-id")

            if self.is_viewed(ads_id):
                continue
            self.viewed_list.append(ads_id)
            data = {
                'name': name,
                'description': description,
                'url': url,
                'price': price
            }
            """Определяем нужно ли нам учитывать ключевые слова"""
            if self.keys_word != ['']:
                if any([item.lower() in (description.lower() + name.lower()) for item in self.keys_word]) \
                        and \
                        self.min_price <= int(price) <= self.max_price:
                    data = self.__parse_full_page(url, data)
                    self.__pretty_log(data=data)
            elif self.min_price <= int(price) <= self.max_price:
                data = self.__parse_full_page(url, data)
                self.__pretty_log(data=data)
            else:
                continue
        self.__save_viewed()

    def __pretty_log(self, data):
        """Красивый вывод"""
        logger.success(
            f'\n{data.get("name", "-")}\n'
            f'Цена: {data.get("price", "-")}\n'
            f'Описание: {data.get("description", "-")}\n'
            f'Просмотров: {data.get("views", "-")}\n'
            f'Дата публикации: {data.get("date_public", "-")}\n'
            f'Продавец: {data.get("seller_name", "-")}\n'
            f'Ссылка: {data.get("url", "-")}\n')

    def __parse_full_page(self, url: str, data: dict) -> dict:
        """Парсит для доп. информации открытое объявление на отдельной вкладке"""
        self.driver.switch_to_window(window=1)
        self.driver.get(url)

        """Если не дождались загрузки"""
        try:
            self.driver.wait_for_element(LocatorAvito.TOTAL_VIEWS[1], by="css selector", timeout=10)
        except Exception:
            """Проверка на бан по ip"""
            if "Доступ ограничен" in self.driver.get_title():
                logger.success("Доступ ограничен: проблема с IP. \nПоследние объявления будут без подробностей")

            self.driver.switch_to_window(window=0)
            return data

        """Количество просмотров"""
        if self.driver.find_elements(LocatorAvito.TOTAL_VIEWS[1], by="css selector" ):
            total_views = self.driver.find_element(LocatorAvito.TOTAL_VIEWS[1]).text.split()[0]
            data["views"] = total_views

        """Дата публикации"""
        if self.driver.find_elements(LocatorAvito.DATE_PUBLIC[1], by="css selector"):
            date_public = self.driver.find_element(LocatorAvito.DATE_PUBLIC[1], by="css selector").text
            if "· " in date_public:
                date_public = date_public.replace("· ", '')
            data["date_public"] = date_public

        """Имя продавца"""
        if self.driver.find_elements(LocatorAvito.SELLER_NAME[1], by="css selector"):
            seller_name = self.driver.find_element(LocatorAvito.SELLER_NAME[1], by="css selector").text
            data["seller_name"] = seller_name

        """Возвращается на вкладку №1"""
        self.driver.switch_to_window(window=0)
        return data

    def is_viewed(self, ads_id: str) -> bool:
        """Проверяет, смотрели мы это или нет"""
        if ads_id in self.viewed_list:
            return True
        return False

    def __save_viewed(self):
        """Сохраняет просмотренные объявления"""
        with open('viewed.txt', 'w') as file:
            for item in set(self.viewed_list):
                file.write(f"{item}\n")


    def parse(self):
        """Метод для вызова"""
        with SB(uc=True,
                headless=True,
                page_load_strategy="eager",
                block_images=True,
                skip_js_waits=True,
                ) as self.driver:
            try:
                self.__get_url()
                self.__paginator()
            except Exception as error:
                logger.error(f"Ошибка: {error}")



if __name__ == '__main__':
    """Здесь заменить данные на свои"""
    import configparser

    config = configparser.ConfigParser()  # создаём объекта парсера
    config.read("settings.ini")  # читаем конфиг
    url = config["Avito"]["URL"]
    chat_id = config["Avito"]["CHAT_ID"]
    token = config["Avito"]["TG_TOKEN"]
    num_ads = config["Avito"]["NUM_ADS"]
    freq = config["Avito"]["FREQ"]
    keys = config["Avito"]["KEYS"]
    max_price = config["Avito"].get("MAX_PRICE", "0")
    min_price = config["Avito"].get("MIN_PRICE", "0")

    if token and chat_id:
        params = {
            'token': token,
            'chat_id': chat_id
        }
        tg_handler = NotificationHandler("telegram", defaults=params)

        """Все логи уровня SUCCESS и выше отсылаются в телегу"""
        logger.add(tg_handler, level="SUCCESS", format="{message}")

    while True:
        try:
            AvitoParse(
                url=url,
                count=int(num_ads),
                keysword_list=keys.split(","),
                max_price=int(max_price),
                min_price=int(min_price)
            ).parse()
            logger.info("Пауза")
            time.sleep(int(freq) * 60)
        except Exception as error:
            logger.error(error)
            logger.error('Произошла ошибка, но работа будет продолжена через 30 сек. '
                         'Если ошибка повторится несколько раз - перезапустите скрипт.'
                         'Если и это не поможет - обратитесь к разработчику по ссылке ниже')
            time.sleep(30)
