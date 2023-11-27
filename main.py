from flask import Flask, jsonify, request
import requests
import re
from bs4 import BeautifulSoup
import json

app = Flask(__name__)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

@app.route('/')
def welcome():
    return "Welcome to moviedrive api! 🎉"

@app.route('/kezdolap', methods=['GET'])
def scrape_moviedrive():
    url = "https://moviedrive.hu/kezdolap/"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    today_cards = soup.find_all('div', class_='card card--big')
    todaypopular = extract_cards_info(today_cards)

    week_cards = soup.find_all('div', class_='card card--list')
    weekpopular = extract_cards_info(week_cards, include_description=True)

    new_upload_cards = soup.find_all('div', class_='card')
    newuploads = extract_cards_info(new_upload_cards, include_views=False)

    return jsonify({"todaypopular": todaypopular, "weekpopular": weekpopular, "newuploads": newuploads})

def extract_cards_info(cards, include_description=False, include_views=True):
    card_list = []
    for card in cards:
        movie = {}
        movie['type'] = card.find('span', class_='card__type').text
        movie['poster'] = card.find('img')['src']
        movie['title'] = card.find('h3', class_='card__title').a.text
        movie['category'] = [genre.text for genre in card.find_all('a', href=lambda href: href and "genere" in href)]

        score_views_text = card.find('span', class_='card__rate').text.strip().split()
        movie['score'] = float(score_views_text[0]) if score_views_text else None
        movie['views'] = int(score_views_text[1].replace(',', '')) if len(score_views_text) > 1 else None

        if include_description:
            desc = card.find('div', class_='card__description')
            movie['description'] = desc.p.text if desc else ''

        if not include_views and movie['views'] is not None:
            continue

        card_list.append(movie)
    return card_list

@app.route('/search')
def search():
    query = request.args.get('q', '')
    search_url = f"https://moviedrive.hu/filmek/?q={query}"
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    search_results = extract_cards_info(soup.find_all('div', class_='card'))

    return jsonify({"searchResults": search_results})

def get_total_pages():
    url = "https://moviedrive.hu/filmek/?p=1000"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    paginator = soup.find('ul', class_='paginator')
    if paginator:
        total_pages = paginator.find_all('li')[-2].text.strip()
        return total_pages
    return 'Unknown'

@app.route('/tartalmak')
def movies():
    page_number = request.args.get('p', '1')
    movies_url = f"https://moviedrive.hu/filmek/?p={page_number}"
    response = requests.get(movies_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    movie_cards = soup.find_all('div', class_='card')
    movies_data = extract_cards_info(movie_cards)

    total_pages = get_total_pages()

    return jsonify({"currentPage": page_number, "totalPages": total_pages, "movies": movies_data})

@app.route('/sorozatok', methods=['GET'])
def series():
    series_id = request.args.get('id', '')
    evad = request.args.get('evad', None)
    episode = request.args.get('episode', None)

    series_url = f"https://moviedrive.hu/sorozat/?id={series_id}"
    series_url += f"&evad={evad}" if evad else ''
    response = requests.get(series_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    series_data = {}

    title = soup.find('h1', class_='details__title')
    series_data['title'] = title.text.strip() if title else 'Unknown'
    series_data['current_season'] = evad if evad else 'All seasons'

    card = soup.find('div', class_='card card--details card--series')
    if card:
        image = card.find('div', class_='card__cover').find('img')['src']
        series_data['poster'] = image

        rating = card.find('span', class_='card__rate')
        series_data['rating'] = rating.text.strip() if rating else 'Unknown'

        genres = card.find_all('a', href=lambda href: href and "genere" in href)
        series_data['category'] = [genre.text for genre in genres]

        meta = card.find_all('li')
        for item in meta:
            text = item.text.strip().split(':')
            if len(text) == 2:
                key, value = text
                key_lower = key.strip().lower()
                if key_lower == "műfaj":
                    continue
                elif key_lower == "kiadás év":
                    series_data['release'] = value.strip()
                elif key_lower == "hossz":
                    series_data['length'] = value.strip()
                elif key_lower == "ország":
                    series_data['country'] = value.strip()
                elif key_lower == "összes megtekintés":
                    series_data['views'] = value.strip()

        description = card.find('div', class_='card__description')
        series_data['description'] = description.text.strip() if description else 'Unknown'

    evad_parent = soup.find('div', class_='evad-parent')
    if evad_parent:
        spans = evad_parent.find_all('span')
        series_data['evad_spans'] = [span.text.strip() for span in spans]
        
    series_data['episodes'] = []
    episode_divs = soup.find_all('div', class_='col-12 col-lg-3 col-md-4 mt-2')
    for div in episode_divs:
        button = div.find('button')
        if button:
            episode_name = button.find('span').text.strip()
            series_data['episodes'].append(episode_name)

    if evad and episode:
        episode_url = f"https://moviedrive.hu/sorozat/?id={series_id}&evad={evad}&ep={episode}"
        episode_response = requests.get(episode_url, headers=headers)
        episode_soup = BeautifulSoup(episode_response.text, 'html.parser')
        iframe = episode_soup.find('iframe', id='player')
        if iframe and 'src' in iframe.attrs:
            current_episode_match = re.search(r'ep=(\d+)', iframe['src'])
            if current_episode_match:
                current_episode_number = int(current_episode_match.group(1)) - 1

                episode_int = int(episode)

                new_episode_number = current_episode_number + episode_int

                new_embed_link = re.sub(r'ep=\d+', f'ep={new_episode_number}', iframe['src'])
                embed_url = new_embed_link

                video_response = requests.get(embed_url, headers=headers)
                video_soup = BeautifulSoup(video_response.text, 'html.parser')

                video_sources = []
                script_tag = video_soup.find('script', string=re.compile('player.source'))
                if script_tag:
                    js_code = script_tag.string.strip()

                    match = re.search(r'player\.source\s*=\s*\{\s*type:\s*\'video\',\s*sources:\s*\[([^\]]+)\]', js_code, re.DOTALL)
                    if match:
                        sources_array = match.group(1)
                        sources_array = sources_array.replace("'", '"').replace("\n", "").replace("        ", "").strip()
                        formatted_sources = sources_array.replace("src: ", '"src": ').replace("type: ", '"type": ').replace("size: ", '"size": ')
                        formatted_sources = re.sub(r',\s*(?=[\]}])', '', formatted_sources)
                        formatted_sources = formatted_sources.rstrip(',')
                        
                        video_sources = json.loads(f'[{formatted_sources}]')

                series_data['episode_embed_link'] = new_embed_link
                series_data['video_sources'] = video_sources


    return jsonify(series_data)

@app.route('/filmek', methods=['GET'])
def film_details():
    input_id = request.args.get('id', '')
    film_data = {}
    
    video_url = f"https://moviedrive.hu/embed/?id={input_id}"
    video_response = requests.get(video_url, headers=headers)
    video_soup = BeautifulSoup(video_response.text, 'html.parser')

    video_sources = []
    script_tag = video_soup.find('script', string=re.compile('player.source'))
    js_code = script_tag.string.strip()
    match = re.search(r'player\.source\s*=\s*\{\s*type:\s*\'video\',\s*sources:\s*\[([^\]]+)\]', js_code, re.DOTALL)
    if match:
        sources_array = match.group(1)
        sources_array = sources_array.replace("'", '"').replace("\n", "").replace("        ", "").strip()
        formatted_sources = sources_array.replace("src: ", '"src": ').replace("type: ", '"type": ').replace("size: ", '"size": ')
        formatted_sources = re.sub(r',\s*(?=[\]}])', '', formatted_sources)
        formatted_sources = formatted_sources.rstrip(',')
        video_sources = json.loads(f'[{formatted_sources}]')

    film_url = f"https://moviedrive.hu/film/?id={input_id}"
    response = requests.get(film_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title = soup.find('h1', class_='details__title')
    film_data['title'] = title.text.strip() if title else 'Unknown'

    movie_card = soup.find('div', class_='col-12 col-xl-11')
    card = soup.find('div', class_='card card--details card--series')
    if card:
        image = card.find('div', class_='card__cover').find('img')['src']
        film_data['poster'] = image

        rating = card.find('span', class_='card__rate')
        film_data['rating'] = rating.text.strip() if rating else 'Unknown'

        genres = card.find_all('a', href=lambda href: href and "genere" in href)
        film_data['category'] = [genre.text for genre in genres]

        meta = card.find_all('li')
        for item in meta:
            text = item.text.strip().split(':')
            if len(text) == 2:
                key, value = text
                key_lower = key.strip().lower()
                if key_lower == "műfaj":
                    continue 
                elif key_lower == "kiadás év":
                    film_data['release'] = value.strip()
                elif key_lower == "hossz":
                    film_data['length'] = value.strip()
                elif key_lower == "ország":
                    film_data['country'] = value.strip()
                elif key_lower == "összes megtekintés":
                    film_data['views'] = value.strip()

        description = card.find('div', class_='card__description')
        film_data['description'] = description.text.strip() if description else 'Unknown'
        film_data['video_sources'] = video_sources

    return jsonify(film_data)

if __name__ == '__main__':
    app.run(debug=True)
