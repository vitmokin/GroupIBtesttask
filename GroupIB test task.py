import re
import urllib.parse
import urllib.request
from datetime import date, timedelta
from time import sleep


def date_description_to_date(string):
    """Translates date description to YYYY-MM-DD format"""
    today = date.today()
    if "сегодня" in string.lower():
        return today.isoformat()
    if "вчера" in string.lower():
        return (today - timedelta(days=1)).isoformat()
    else:
        original_day = int(re.search(r"(\d*) *", string).groups()[0])
        new_date = date(year=today.year, month=today.month, day=original_day)
        if new_date.day > today.day:
            # Тут надо вычесть один месяц
            # Я не хочу прописывать руками, в каком месяце сколько дней и думать про високосные года
            # Поэтому я вычитаю 1 день до тех пор, пока день снова не совпадёт
            # Согласен, уродливо
            while new_date.month == today.month or new_date.day != original_day:
                new_date -= timedelta(days=1)
        return new_date.isoformat()


def is_page_last(page):
    if not re.search("pagination-button/next", page) or re.search(
            "pagination-button/next(.+)pagination-item_readonly",
            page):
        return False
    else:
        return True


def get_ids_from_page(search, page_number=1):
    """Returns list of items id and is this page not the last one"""
    # Первый запрос работает нормально, второй запрос - ошибка 429 Too Many Request
    # Как бороться - непонятно, и не факт, что вообще возможно
    # Скорее всего - это защита от DDOS-атак на их сервере и её не обойти без смены IP после каждого запроса
    # По идее, если у нас много прокси и мы можем их часто менять, проблемы не будет
    values = {'q': search}
    if page_number != 1:
        values['p'] = page_number
    req = urllib.request.urlopen('https://www.avito.ru/?' + urllib.parse.urlencode(values))
    with req as response:
        page = str(response.read())
    return re.findall(r'data-item-id="(\d+)"', page), is_page_last(page)


class AvitoParser:

    def get_all_ids(self, search):
        """Returns all ids of items of the search"""
        all_id = list()
        page_number = 1
        result = get_ids_from_page(search)
        all_id.extend(result[0])
        while result[1]:
            sleep(self.timestamp)
            page_number += 1
            result = get_ids_from_page(search, page_number)
            all_id.extend(result[0])
        # print(all_id)
        return all_id

    def parser(self, dictionary):
        """Gets a dictionary with a search (string) and a callback adress (optional) and returns a list of parsed
        items """
        search = dictionary["search"]
        all_items_info_list = list()
        wrong_id = list()
        try:
            ids = self.get_all_ids(self, search)
        except urllib.error.HTTPError as err:
            print(err)
            return None
        for item_id in ids:
            # Иногда Авито кидает ошибку 429 Too Many Request, чтобы не ловить её постоянно, приходится замедлять код
            # Даже после замедления ошибка иногда прилетает, поэтому id с такими ошибками просто записываем отдельно
            # Если существует способ обойти её адекватнее, это всё можно удалить и всё ускорится
            sleep(self.timestamp)
            try:
                req = urllib.request.urlopen('https://www.avito.ru/' + str(item_id))
            except urllib.error.HTTPError:
                wrong_id.append(item_id)
            else:
                with req as response:
                    page = response.read()
                item_info = dict()
                item_info['title'] = re.search(
                    b'class="title-info-title-text" itemprop="name">(.*)</span>\\n </h1> </div> <div '
                    b'id="toggle-sticker-header"',
                    page).groups()[0].decode()
                item_info['desc'] = re.search(
                    b'title="(?:[^"]+)"> <span itemprop="name">([^<]+)</span> </a> <meta itemprop="position" '
                    b'content="4"> '
                    b'</span>',
                    page).groups()[0].decode()
                item_info['url'] = 'https://www.avito.ru/' + str(item_id)
                item_info['price'] = re.search(b'itemprop="price" content="(\d+(?:\.\d{1,2})?)', page).groups()[
                    0].decode()
                item_info['pubDate'] = date_description_to_date(
                    re.search(b'<div class="title-info-metadata-item-redesign">\s*([^<]+)\s*</div>', page).groups()[
                        0].decode())
                all_items_info_list.append(item_info)
        # TODO: поменять принты на логгирование
        # print("errors number :", len(wrong_id), "errors was on ids:", wrong_id)
        return all_items_info_list

    def __new__(self, dictionary):
        self.timestamp = 10
        result = self.parser(self, dictionary)
        if 'callback_address' in dictionary:
            urllib.request.urlopen(dictionary['callback_address'], data=urllib.parse.urlencode(result).encode())
        else:
            return result


# test request
# testing = AvitoParser({"search": "Rowenta CV8250"})
# print(testing)
# TODO: GRCP и прокси можно добавить через либу Grab в несколько строчек, насколько я понимаю
# TODO: С номером телефона гораздо веселее - там надо нажать на кнопку, забрать картинку с номером и распознать его
# TODO: нажать на кнопку можно с помощью либы selenium, 4 строки вроде бы
# TODO: получить картинку можно через urllib, распознать цифры - pytesseract
