from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import yfinance as yf
import urllib.request
import xml.etree.ElementTree as ET
import google.generativeai as genai
import pandas as pd
import json
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Borsa Analiz Paneli API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )

EXCEL_KAYNAK = "A.xlsx"

def hisse_listesini_al():
    try:
        df = pd.read_excel(EXCEL_KAYNAK)
        liste = df.iloc[:, 0].dropna().unique().tolist()
        return [str(h).strip().split()[0] for h in liste]
    except Exception as e:
        print(f"Excel okuma hatası: {e}. Varsayılan liste gönderiliyor.")
        return ["THYAO", "ASELS", "SASA", "GARAN", "KCHOL"]

def haber_verilerini_getir(hisse_kodu: str):
    haber_basliklari = []
    hisse_kodu = hisse_kodu.upper()
    kodlar_denenecek = [hisse_kodu]
    if not hisse_kodu.endswith(".IS"):
        kodlar_denenecek.append(f"{hisse_kodu}.IS")
        
    for kod in kodlar_denenecek:
        try:
            hisse = yf.Ticker(kod)
            haberler = hisse.news
            if haberler:
                return [haber['title'] for haber in haberler]
        except Exception:
            continue 

    aramalar = [
        (f"{hisse_kodu}+hisse+haber", "hl=tr&gl=TR&ceid=TR:tr"), 
        (f"{hisse_kodu}+stock+news", "hl=en-US&gl=US&ceid=US:en") 
    ]
    
    for sorgu, dil_ayari in aramalar:
        try:
            url = f"https://news.google.com/rss/search?q={sorgu}&{dil_ayari}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)
            for item in root.findall('.//item'):
                haber_basliklari.append(item.find('title').text)
                if len(haber_basliklari) >= 15:
                    break
            if haber_basliklari:
                return haber_basliklari
        except Exception:
            continue
    return []

@app.get("/api/hisseler")
async def listeyi_gonder():
    return hisse_listesini_al()

@app.get("/api/borsa/{hisse}/{periyot}")
async def veri_isleme(hisse: str, periyot: str):
    ayarlar = {
        "1gun": {"p": "1d", "i": "1m"},
        "1ay":  {"p": "1mo", "i": "1d"},
        "6ay":  {"p": "6mo", "i": "1d"},
        "12ay": {"p": "1y", "i": "1d"}
    }
    secim = ayarlar.get(periyot, ayarlar["1ay"])
    
    try:
        symbol = f"{hisse.upper()}.IS"
        
        df_frontend = yf.download(symbol, period=secim["p"], interval=secim["i"])
        
        if df_frontend.empty:
            raise HTTPException(status_code=404, detail="Veri bulunamadı")

        df_matlab = yf.download(symbol, period="1y", interval="1d")
        df_matlab.reset_index(inplace=True) 
        
        if isinstance(df_matlab.columns, pd.MultiIndex):
            df_matlab.columns = df_matlab.columns.get_level_values(0)
            
        if 'Datetime' in df_matlab.columns:
            df_matlab['Datetime'] = df_matlab['Datetime'].dt.tz_localize(None) 
            df_matlab.rename(columns={'Datetime': 'Date'}, inplace=True)
            
        df_matlab.to_excel("Share_data.xlsx", index=False)

        if periyot == "1gun":
            dates = df_frontend.index.strftime('%H:%M').tolist()
        else:
            tr_aylar = {
                "Jan": "Ocak", "Feb": "Şubat", "Mar": "Mart", "Apr": "Nisan",
                "May": "Mayıs", "Jun": "Haziran", "Jul": "Temmuz", "Aug": "Ağustos",
                "Sep": "Eylül", "Oct": "Ekim", "Nov": "Kasım", "Dec": "Aralık"
            }
            dates = []
            for d in df_frontend.index:
                gun_ay = d.strftime('%d %b')
                for ing, tr in tr_aylar.items():
                    gun_ay = gun_ay.replace(ing, tr)
                dates.append(gun_ay)

        prices = df_frontend['Close'].iloc[:, 0].tolist() if isinstance(df_frontend['Close'], pd.DataFrame) else df_frontend['Close'].tolist()
        
        return {
            "symbol": hisse.upper(),
            "current_price": round(float(prices[-1]), 2),
            "dates": dates,
            "prices": [round(float(p), 2) for p in prices]
        }
    except Exception as e:
        print(f"Borsa veri indirme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def yapay_zeka_tahmini(df):
    try:
        df = df.copy()
        df.sort_values('Date', ascending=True, inplace=True)

        df['DailyRange'] = df['Close'] - df['Open']
        df['PriceRange'] = df['High'] - df['Low']

        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        df['ShortEMA'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['LongEMA'] = df['Close'].ewm(span=26, adjust=False).mean()

        df['MACD_Line'] = df['ShortEMA'] - df['LongEMA']
        df['MACD'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()

        df['LogReturn'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Lag1_Return'] = df['LogReturn'].shift(1)
        df['Lag2_Return'] = df['LogReturn'].shift(2)
        df['Lag3_Return'] = df['LogReturn'].shift(3)

        df['Dist_ShortEMA'] = (df['Close'] - df['ShortEMA']) / df['ShortEMA']
        df['Dist_LongEMA'] = (df['Close'] - df['LongEMA']) / df['LongEMA']

        df['NextDayReturn'] = (df['Close'].shift(-1) - df['Close']) / df['Close']
        df['Target'] = (df['NextDayReturn'] > 0.0).astype(float)

        features = ["RSI", "MACD", "Volume", "DailyRange", "PriceRange", 
                    "Lag1_Return", "Lag2_Return", "Lag3_Return", 
                    "Dist_ShortEMA", "Dist_LongEMA"]

        last_day_features = df.iloc[-1:][features]

        train_df = df.iloc[:-1].dropna(subset=features + ['Target'])

        if len(train_df) < 50:
            return {"hata": "Analiz için yeterli veri yok (En az 50 gün gerekli)."}

        X_train = train_df[features]
        y_train = train_df['Target']

        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X_train, y_train)

        tahmin_sinifi = model.predict(last_day_features)[0]
        ihtimaller = model.predict_proba(last_day_features)[0]

        return {
            "tahmin": int(tahmin_sinifi),
            "yukselis_ihtimali": float(ihtimaller[1]),
            "dusus_ihtimali": float(ihtimaller[0]),  
        }
    except Exception as e:
        return {"hata": f"Python Yapay Zeka Hatası: {str(e)}"}

@app.get("/api/tahmin_matlab")
async def python_tahmini_getir():
    dosya_yolu = 'Share_data.xlsx'
    
    if os.path.exists(dosya_yolu):
        try:
            df = pd.read_excel(dosya_yolu)
            sonuc = yapay_zeka_tahmini(df)
            return sonuc
        except Exception as e:
            return {"hata": "Excel okunamadı veya analiz edilemedi."}
    else:
        return {"hata": "Veri dosyası (Share_data.xlsx) bulunamadı."}
    dosya_yolu = 'tahmin_sonucu.json'

    if os.path.exists(dosya_yolu):
        try:
            os.remove(dosya_yolu)
        except:
            pass

    try:
        subprocess.run(["matlab", "-wait", "-batch", "test"], shell=True, check=True)
    except Exception as e:
        return {"hata": "MATLAB bilgisayarda bulunamadı veya çalıştırılamadı."}

    if os.path.exists(dosya_yolu):
        try:
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"hata": "JSON okunamadı."}
    else:
        return {"hata": "MATLAB arka planda hata verdi (Kod çökmesi)."}
    
    dosya_yolu = 'tahmin_sonucu.json'
    if os.path.exists(dosya_yolu):
        try:
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
                veri = json.load(f)
            return veri
        except Exception as e:
            raise HTTPException(status_code=500, detail="MATLAB veri dosyası okunamadı.")
    else:
        return {"tahmin": None, "yukselis_ihtimali": 0, "dusus_ihtimali": 0, "hata": "MATLAB analizi henüz çalıştırılmadı."}

@app.get("/api/analiz_gemini/{hisse_kodu}")
async def hisse_analiz_et(hisse_kodu: str):
    if not GOOGLE_API_KEY:
        return {"kullanici_raporu": "API Anahtarı eksik. Lütfen .env dosyasını kontrol edin.", "sayisal_skor": 0.0}

    haberler = haber_verilerini_getir(hisse_kodu)
    if not haberler:
         return {"kullanici_raporu": "Bu hisse için son günlerde yeterli veya anlamlı haber bulunamadı.", "sayisal_skor": 0.0}

    haber_metni = "\n".join(haberler)
    prompt = f"""
    Sen uzman bir Wall Street finansal analistisin. 
    Aşağıda '{hisse_kodu}' hissesine ait en güncel haber başlıkları verilmiştir:
    
    {haber_metni}
    
    Lütfen bu haberlerin şirketin geleceği üzerindeki genel duyarlılığını (sentiment) analiz et. 
    Sadece aşağıdaki yapıda, geçerli bir JSON döndür. Başka hiçbir açıklama yazma:
    {{
        "sayisal_skor": 0.5,
        "kullanici_raporu": "Rapor metni buraya..."
    }}
    """
    try:
        response = model.generate_content(prompt)
        cevap_metni = response.text.strip()
        
        if cevap_metni.startswith("```json"):
            cevap_metni = cevap_metni[7:]
        if cevap_metni.endswith("```"):
            cevap_metni = cevap_metni[:-3]
        
        cevap_metni = cevap_metni.strip()
        
        gemini_analizi = json.loads(cevap_metni)
        
        return {
            "hisse_kodu": hisse_kodu.upper(),
            "sayisal_skor": float(gemini_analizi.get("sayisal_skor", 0.0)), 
            "kullanici_raporu": gemini_analizi.get("kullanici_raporu", "Rapor oluşturulamadı.")
        }
    except Exception as e:
        print(f"\n--- GEMINI HATASI --- \nDetay: {e}\nCevap Metni: {response.text if 'response' in locals() else 'Cevap alınamadı'}")
        
        return {
            "kullanici_raporu": f"Bağlantı veya JSON hatası: {str(e)[:50]}...", 
            "sayisal_skor": 0.0
        }
    
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)