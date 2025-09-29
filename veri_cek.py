# veri_cek.py dosyasının yeni ve doğru hali
from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc
import random
from datetime import datetime
import requests

# TMDB API bağlantı bilgileri
API_KEY = '3ab76386939fdbf56e4b345f56b53258'

# Veritabanı bağlantı bilgileri
SERVER = 'localhost'
DATABASE = 'FilmOnermeSistemi'
USERNAME = 'SA'
PASSWORD = 'reallyStrongPwd123'

# --- ÖNCE FONKSİYON TANIMI ---
def get_genres():
    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={API_KEY}&language=tr-TR"
    response = requests.get(url)
    if response.status_code == 200:
        genres_data = response.json().get('genres', [])
        return {genre['id']: genre['name'] for genre in genres_data}
    return {}

# --- SONRA FONKSİYON ÇAĞRISI ---
GENRE_MAP = get_genres()

def get_db_connection():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}')
    return conn

def get_movies_from_tmdb(page=1):
    try:
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={API_KEY}&language=tr-TR&page={page}"
        response = requests.get(url)
        response.raise_for_status()  # HTTP hataları için bir istisna fırlatır
        data = response.json()
        return data.get('results', [])
    except requests.exceptions.RequestException as e:
        print(f"TMDB API'ye bağlanırken bir hata oluştu: {e}")
        return [] # Boş bir liste döndürerek uygulamanın çökmesini engeller

def save_movies_to_db(movies):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for movie in movies:
        try:
            title = movie.get('title')
            release_year = movie.get('release_date', '')[:4]
            imdb_rating = movie.get('vote_average')
            genres = ', '.join([GENRE_MAP.get(g, 'Bilinmeyen') for g in movie.get('genre_ids', [])])
            poster_url = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}"

            cursor.execute("SELECT FilmID FROM Filmler WHERE Baslik = ? AND Yil = ?", (title, release_year))
            if cursor.fetchone():
                print(f"'{title}' zaten veritabanında mevcut, atlanıyor.")
                continue

            sql = """
            INSERT INTO Filmler (FilmID, Baslik, Yil, Turler, IMDBPuani, PosterURL)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            # movie.get('id') TMDB numarasını verir, bu da bizim yeni FilmID'mizdir.
            cursor.execute(sql, (movie.get('id'), title, release_year, genres, imdb_rating, poster_url)) 

            print(f"'{title}' veritabanına eklendi.")
        except pyodbc.Error as ex:
            print(f"Hata: {movie.get('title')} filmi eklenirken bir sorun oluştu. {ex}")

    conn.commit()
    conn.close()
    print("Tüm filmler veritabanına başarıyla eklendi.")
    
# Not: if __name__ == '__main__': bloğunu kaldırdık, çünkü bu dosya artık başka bir dosya tarafından çağrılıyor.
# Bu kısmı dosyanın en altına ekleyin.
if __name__ == '__main__':
    print("TMDB'den filmler çekiliyor...")
    # 10 sayfa film çekmek için
    all_movies = []
    for page in range(1, 11):
        movies = get_movies_from_tmdb(page)
        all_movies.extend(movies)

    if all_movies:
        save_movies_to_db(all_movies)
    else:
        print("Filmler çekilemedi. API anahtarınızı veya internet bağlantınızı kontrol edin.")