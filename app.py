from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc
import random
from datetime import datetime
import requests
import os

app = Flask(__name__)
app.secret_key = 'film_oneri_sistemi_gizli_anahtar'
API_KEY = '3ab76386939fdbf56e4b345f56b53258'

# Veritabanı bağlantı bilgileri
SERVER = 'localhost'
DATABASE = 'FilmOnermeSistemi'
USERNAME = 'SA'
PASSWORD = 'reallyStrongPwd123'

# --- TMDB'den film türlerini çeken fonksiyon ---
# Bu fonksiyon, diğer fonksiyonlar tarafından kullanılmadan önce tanımlanmalıdır.
def get_genres():
    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={API_KEY}&language=tr-TR"
    response = requests.get(url)
    if response.status_code == 200:
        genres_data = response.json().get('genres', [])
        return {genre['id']: genre['name'] for genre in genres_data}
    return {}

# --- Fonksiyon tanımından sonra çağrılması önemlidir ---
GENRE_MAP = get_genres()

# --- Veritabanı Bağlantı Fonksiyonu ---
def get_db_connection():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}')
    return conn

# --- Uygulama Yönlendirmeleri (Routes) ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    sql_kullanici = "SELECT KullaniciAdi FROM Kullanicilar WHERE KullaniciID = ?"
    cursor.execute(sql_kullanici, (session['user_id']))
    
    kullanici = cursor.fetchone()
    conn.close()
    
    if kullanici:
        kullanici_adi = kullanici.KullaniciAdi
        return render_template('index.html', kullanici_adi=kullanici_adi)
    else:
        session.pop('user_id', None)
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            sql = "INSERT INTO Kullanicilar (KullaniciAdi, Email, Sifre) VALUES (?, ?, ?)"
            cursor.execute(sql, (username, email, password))
            conn.commit()
            return redirect(url_for('login'))
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            if sqlstate == '23000':
                return "Bu kullanıcı adı veya e-posta adresi zaten kullanılıyor. Lütfen başka bir tane deneyin."
            return f"Bir hata oluştu: {sqlstate}"
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = "SELECT KullaniciID, KullaniciAdi FROM Kullanicilar WHERE Email = ? AND Sifre = ?"
        cursor.execute(sql, (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user.KullaniciID
            return redirect(url_for('index'))
        else:
            return "Giriş başarısız. Lütfen bilgilerinizi kontrol edin."
    
    return render_template('login.html')

# app.py dosyası içinde, @app.route('/izledim/<int:film_id>', methods=['POST']) fonksiyonu

@app.route('/izledim/<int:film_id>', methods=['POST'])
def izledim(film_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Filmi İzleme Geçmişine EKLE (INSERT)
        sql_izle = "INSERT INTO KullaniciIzlemeGecmisi (KullaniciID, FilmID, IzlemeTarihi) VALUES (?, ?, ?)"
        cursor.execute(sql_izle, (session['user_id'], film_id, datetime.now()))
        
        # 👇 2. Öneri Geçmişinden SİL (DELETE) - Bu kısım eklendi!
        sql_sil = "DELETE FROM KullaniciOneriGecmisi WHERE KullaniciID = ? AND FilmID = ?"
        cursor.execute(sql_sil, (session['user_id'], film_id))
        
        conn.commit()
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        # '23000' Benzersiz kısıtlama ihlali hatası yakalandı
        if sqlstate == '23000':
             print(f"UYARI: Kayıt tekrarı. Film ID {film_id} zaten izlenmiş olarak kaydedilmiş. (Yoksayılıyor)")
             
             # Eğer izleme geçmişinde zaten varsa, sadece öneri geçmişinden silmeyi denemek için commit yapalım
             try:
                 sql_sil = "DELETE FROM KullaniciOneriGecmisi WHERE KullaniciID = ? AND FilmID = ?"
                 cursor.execute(sql_sil, (session['user_id'], film_id))
                 conn.commit()
             except pyodbc.Error as ex_sil:
                  print(f"UYARI: Öneri geçmişinden silme hatası: {ex_sil}")
                  
        else:
             print(f"VERİTABANI HATASI (izledim): {ex}")
             return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()
    
    # Kullanıcıyı Profil Sayfasına yönlendir
    return redirect(url_for('profile'))

@app.route('/cevirdaha', methods=['POST'])
def cevirdaha():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    

    son_kategori = session.get('son_kategori')

    if son_kategori:
        return redirect(url_for('oner_film_kategori', kategori=son_kategori))
    else:
        return redirect(url_for('kategori_sec'))

@app.route('/kategori_sec')
def kategori_sec():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Sadece değerleri (tür isimlerini) alıyoruz
    kategoriler = list(GENRE_MAP.values())
    return render_template('kategori_sec.html', kategoriler=kategoriler)

@app.route('/oner_kategori', methods=['GET'])
def oner_film_kategori():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    secilen_kategori = request.args.get('kategori')
    if not secilen_kategori:
        return redirect(url_for('kategori_sec'))
    
    session['son_kategori'] = secilen_kategori

    # Kategori adından TMDB ID'sine dönüşüm
    GENRE_MAP_REVERSE = {v: k for k, v in GENRE_MAP.items()}
    genre_id = GENRE_MAP_REVERSE.get(secilen_kategori)
    
    if not genre_id:
        return render_template('oner.html', film=None, hata_mesaji="Seçilen kategori için film bulunamadı.")

    try:
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&language=tr-TR&sort_by=vote_average.desc&with_genres={genre_id}&vote_count.gte=1000&page=1"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        filmler = data.get('results', [])
        
        if filmler:
            film = random.choice(filmler)

            # Oneri için gerekli film verilerini oluştur
            onerilen_film = {
                'Baslik': film.get('title'),
                'Yil': film.get('release_date', '')[:4],
                'Turler': secilen_kategori,
                'IMDBPuani': film.get('vote_average'),
                'PosterURL': f"https://image.tmdb.org/t/p/w500{film.get('poster_path')}",
                'FilmID': film.get('id')
            }
            
            # Seçilen filmi veritabanına kaydet
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Eğer film veritabanında yoksa ekle
            cursor.execute("SELECT FilmID FROM Filmler WHERE FilmID = ?", (onerilen_film['FilmID'],))
            if not cursor.fetchone():
                sql_film_ekle = """
                INSERT INTO Filmler (FilmID, Baslik, Yil, Turler, IMDBPuani, PosterURL)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor.execute(sql_film_ekle, (
                    onerilen_film['FilmID'],
                    onerilen_film['Baslik'],
                    onerilen_film['Yil'],
                    onerilen_film['Turler'],
                    onerilen_film['IMDBPuani'],
                    onerilen_film['PosterURL']
                ))
            # Öneri geçmişine filmi ekle
            sql_oneri_kayit = "INSERT INTO KullaniciOneriGecmisi (KullaniciID, FilmID, OneriTarihi) VALUES (?, ?, ?)"
            cursor.execute(sql_oneri_kayit, (session['user_id'], onerilen_film['FilmID'], datetime.now())) 
            
            conn.commit()
            conn.close()

            return render_template('oner.html', film=onerilen_film)
        else:
            return render_template('oner.html', film=None, hata_mesaji="Bu kategori için film bulunamadı. Lütfen başka bir tür deneyin.")

    except requests.exceptions.RequestException as e:
        print(f"TMDB API'den film çekilirken hata oluştu: {e}")
        return render_template('oner.html', film=None, hata_mesaji="Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")
    except Exception as e:
        print(f"Genel hata: {e}")
        return render_template('oner.html', film=None, hata_mesaji="Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Kullanıcı Adı Çekme
        sql_kullanici = "SELECT KullaniciAdi FROM Kullanicilar WHERE KullaniciID = ?"
        cursor.execute(sql_kullanici, (session['user_id']))
        kullanici = cursor.fetchone()
        
        if not kullanici:
            session.pop('user_id', None)
            return redirect(url_for('login'))
            
        kullanici_adi = kullanici[0]
        
        # --- İZLENEN FİLMLER SORGUSU VE DÖNÜŞÜMÜ ---
        # app.py'deki profile() fonksiyonunda izlenen filmler sorgusunu değiştirin:
        # app.py, profile() fonksiyonu içinde (İzlenen filmler sorgusu):
        sql_izlenen = """
        SELECT F.Baslik, F.Yil, F.IMDBPuani, F.PosterURL, F.FilmID
        FROM KullaniciIzlemeGecmisi AS I
        JOIN Filmler AS F ON I.FilmID = F.FilmID  -- Düzeltildi
        WHERE I.KullaniciID = ?
        ORDER BY I.IzlemeTarihi DESC
        """ 
        cursor.execute(sql_izlenen, (session['user_id']))
        columns_izlenen = [column[0] for column in cursor.description]
        izlenen_filmler_raw = cursor.fetchall()
        izlenen_filmler = [dict(zip(columns_izlenen, row)) for row in izlenen_filmler_raw]

        # app.py'deki profile() fonksiyonunda önerilen filmler sorgusunu değiştirin:
        sql_onerilen = """
        SELECT F.Baslik, F.Yil, F.IMDBPuani, F.PosterURL, F.FilmID
        FROM KullaniciOneriGecmisi AS O
        JOIN Filmler AS F ON O.FilmID = F.FilmID  -- Düzeltildi
        WHERE O.KullaniciID = ?
        ORDER BY O.OneriTarihi DESC
        """
        cursor.execute(sql_onerilen, (session['user_id']))
        columns_onerilen = [column[0] for column in cursor.description]
        onerilen_filmler_raw = cursor.fetchall()
        onerilen_filmler = [dict(zip(columns_onerilen, row)) for row in onerilen_filmler_raw]

        # SADECE TEMPLATE'i DÖNDÜR
        # Hata veren Cache-Control satırları kaldırıldı veya basitleştirildi.
        return render_template('profile.html',
                               kullanici_adi=kullanici_adi,
                               izlenen_filmler=izlenen_filmler,
                               onerilen_filmler=onerilen_filmler) 

    except pyodbc.Error as ex:
        # Veritabanı hatası
        print(f"VERİTABANI HATASI (profile): {ex}")
        return redirect(url_for('index'))
    except Exception as e:
        # Genel hata (Artık Jinja2 hatası almamalısınız, ama koruyucu kalkan kalsın)
        print(f"!!! KRİTİK ŞABLON/GENEL HATA (profile): {e}")
        return redirect(url_for('index')) # Kullanıcıyı Ana Sayfaya yönlendir
    finally:
        if conn:
            conn.close()
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/film_detay/<int:film_id>')
def film_detay(film_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    sql_film = "SELECT * FROM Filmler WHERE FilmID = ?"
    cursor.execute(sql_film, (film_id,))
    film = cursor.fetchone()

    if film:
        try:
            url_detay = f"https://api.themoviedb.org/3/movie/{film_id}?api_key={API_KEY}&language=tr-TR"
            response_detay = requests.get(url_detay)
            response_detay.raise_for_status()
            tmdb_detay = response_detay.json()

            overview = tmdb_detay.get('overview', 'Konu bilgisi bulunamadı.')

            url_credits = f"https://api.themoviedb.org/3/movie/{film_id}/credits?api_key={API_KEY}&language=tr-TR"
            response_credits = requests.get(url_credits)
            response_credits.raise_for_status()
            tmdb_credits = response_credits.json()
            
            yonetmenler = [crew['name'] for crew in tmdb_credits.get('crew', []) if crew['job'] == 'Director']
            oyuncular = [cast['name'] for cast in tmdb_credits.get('cast', [])[:5]]

        except requests.exceptions.RequestException as e:
            print(f"TMDB API'den detay çekilirken hata oluştu: {e}")
            overview = 'Konu bilgisi çekilirken hata oluştu.'
            yonetmenler = []
            oyuncular = []
            
        conn.close()
        return render_template('film_detay.html', 
                               film=film, 
                               overview=overview, 
                               yonetmenler=yonetmenler, 
                               oyuncular=oyuncular)

    else:
        conn.close()
        return "Film bulunamadı."

if __name__ == '__main__':
    app.run(debug=True)