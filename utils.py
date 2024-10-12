import requests
from datetime import date

def get_gender_dob(access_token: str) -> tuple[str, date]:
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        "https://people.googleapis.com/v1/people/me?personFields=birthdays,genders",
        headers=headers
    )
    if response.status_code != 200:
        return None, None
    user_info = response.json()
    gender = user_info.get('genders', [])
    if gender:
        gender = gender[0].get('value')
    
    dob = user_info.get('birthdays', [])
    if dob:
        dob = dob[0].get('date', {})
    dob = date(**dob)

    return gender, dob
    