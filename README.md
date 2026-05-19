# 📈 Yapay Zeka Destekli Borsa Analiz Paneli

Bu proje, hisse senedi verilerini canlı olarak çekerek hem makine öğrenmesi (Random Forest) ile kısa vadeli teknik tahminler üreten hem de Google Gemini API kullanarak haberler üzerinden uzun vadeli duyarlılık (sentiment) analizi yapan entegre bir finansal web uygulamasıdır.

## Özellikler

* **Canlı Veri Çekimi:** Yahoo Finance üzerinden anlık ve geçmiş hisse senedi verisi indirme.
* **Kısa Vadeli Tahmin (Teknik Model):** RSI, MACD ve EMA gibi teknik indikatörleri hesaplayarak Scikit-Learn `RandomForestClassifier` ile hissenin ertesi günkü hareketine dair olasılık yüzdesi sunar.
* **Uzun Vadeli Yorum (Piyasa Duyarlılığı):** Google News üzerinden hisseye ait son haberleri tarar ve Gemini 1.5 Pro / Flash modellerini kullanarak yatırımcılar için profesyonel bir duyarlılık raporu oluşturur.
* **Dinamik Grafik (UI):** Chart.js kullanılarak oluşturulmuş, kullanıcı dostu ve karanlık tema (dark mode) destekli modern web arayüzü.

## 🛠️ Kullanılan Teknolojiler

* **Backend:** Python, FastAPI, Uvicorn
* **Yapay Zeka & Veri:** Scikit-Learn, Pandas, NumPy, yfinance, Google Generative AI (Gemini)
* **Frontend:** HTML5, CSS3, JavaScript (Chart.js, Tom Select)

## ⚙️ Kurulum ve Çalıştırma

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin:

**1. Repoyu Klonlayın**
```bash
git clone [https://github.com/KULLANICI_ADIN/proje-adiniz.git](https://github.com/KULLANICI_ADIN/proje-adiniz.git)
cd proje-adiniz
