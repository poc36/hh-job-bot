import openai
import json
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def generate_cover_letter(vacancy, user_profile):
    try:
        prompt = f'''Напиши короткое сопроводительное письмо на русском (2-3 предложения).
Вакансия: {vacancy['title']} @ {vacancy['company']}
Опыт: {user_profile.experience_years} лет, грейд {user_profile.current_grade}

Письмо должно быть профессиональным.'''

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )

        return response["choices"][0]["message"]["content"]
    except:
        return "Спасибо за интересную возможность!"

async def calculate_relevance_score(vacancy, user_profile):
    score = 0

    if vacancy.get("salary_from", 0) and vacancy["salary_from"] >= user_profile.salary_min:
        score += 30

    roles = user_profile.preferred_roles.split(", ")
    title_lower = vacancy["title"].lower()
    for role in roles:
        if role.lower() in title_lower:
            score += 25
            break

    techs = user_profile.preferred_technologies.split(", ")
    desc_lower = (vacancy["description"] + vacancy["title"]).lower()
    tech_matches = sum(1 for t in techs if t.lower() in desc_lower)
    score += min(45, tech_matches * 15)

    return min(100, score)
