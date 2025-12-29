import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup

HH_BASE = "https://hh.ru"

async def search_vacancies(roles, cities, salary_from):
    '''Поиск вакансий через парсинг HH.ru'''
    try:
        city_map = {
            "москва": "113",
            "санкт-петербург": "2",
            "спб": "2",
            "воронеж": "54",
            "remote": "0",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        all_vacancies = []

        for role in roles:
            for city in cities:
                city_id = city_map.get(city.lower())
                if not city_id:
                    continue

                try:
                    url = f"{HH_BASE}/search/vacancy"
                    params = {
                        "text": role,
                        "area": city_id,
                        "salary": salary_from,
                        "currency_code": "RUR",
                        "page": 0,
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                soup = BeautifulSoup(html, 'html.parser')

                                # Ищем все вакансии
                                vacancies = soup.find_all('div', {'class': 'vacancy-card--z_UXteG7nY9cNcHF3xXEKw'})

                                for vac in vacancies[:10]:
                                    try:
                                        # Название
                                        title_elem = vac.find('h3', {'class': 'bloko-header-section-3'})
                                        if not title_elem:
                                            continue

                                        title = title_elem.get_text(strip=True)

                                        # Компания
                                        company_elem = vac.find('div', {'class': 'vacancy-company-name'})
                                        company = company_elem.get_text(strip=True) if company_elem else "Unknown"

                                        # Зарплата
                                        salary_elem = vac.find('span', {'class': 'fake-magritte-primary-text--Hdw8FvkO0MdeN7jHWP_x5w'})
                                        salary_text = salary_elem.get_text(strip=True) if salary_elem else ""

                                        salary_from_val = None
                                        salary_to_val = None
                                        if salary_text and '–' in salary_text:
                                            try:
                                                parts = salary_text.replace(' ', '').split('–')
                                                if len(parts) >= 2:
                                                    salary_from_val = int(parts[0].replace('₽', '').replace(',', ''))
                                                    salary_to_val = int(parts[1].replace('₽', '').replace(',', ''))
                                            except:
                                                pass

                                        # URL
                                        link_elem = vac.find('a', {'class': 'vacancy-card__title-link'})
                                        url = link_elem.get('href', '') if link_elem else ""

                                        # ID
                                        vacancy_id = url.split('/')[-1] if url else ""

                                        # Описание
                                        desc_elem = vac.find('div', {'class': 'vacancy-card__snippet'})
                                        description = desc_elem.get_text(strip=True)[:500] if desc_elem else ""

                                        if title and url:
                                            vacancy = {
                                                "id": vacancy_id,
                                                "title": title,
                                                "company": company,
                                                "salary_from": salary_from_val,
                                                "salary_to": salary_to_val,
                                                "description": description,
                                                "url": url if url.startswith('http') else f"{HH_BASE}{url}",
                                            }

                                            if not any(v["id"] == vacancy["id"] for v in all_vacancies):
                                                all_vacancies.append(vacancy)
                                    except Exception as e:
                                        print(f"⚠️ Ошибка парсинга вакансии: {e}")
                                        continue

                    await asyncio.sleep(1)  # Уважаем HH

                except Exception as e:
                    print(f"⚠️ Ошибка поиска {role} в {city}: {e}")
                    continue

        return all_vacancies

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return []
