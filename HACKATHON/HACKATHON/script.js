let chartInstance;
let ts;
const API_BASE = 'http://127.0.0.1:8000/api';

window.onload = async function() {
    const selector = document.getElementById('hisseKod');
    try {
        const res = await fetch(`${API_BASE}/hisseler`);
        const hisseler = await res.json();
        
        selector.innerHTML = '<option value="">Hisse Seçiniz...</option>';
        hisseler.forEach(hisse => {
            let option = document.createElement('option');
            option.value = hisse;
            option.text = hisse;
            selector.appendChild(option);
        });

        ts = new TomSelect("#hisseKod", {
            create: false,
            sortField: { field: "text", direction: "asc" },
            placeholder: "Hisse ismi yazın...",
            maxOptions: 500
        });

    } catch (err) {
        console.error("Liste yüklenemedi:", err);
    }
};

async function veriyiGuncelle() {
    const hisse = ts.getValue();
    const period = document.querySelector('input[name="period"]:checked').value;
    const status = document.getElementById('tahminDurum');
    const priceDiv = document.getElementById('fiyatText');
    const baslik = document.getElementById('baslik');
    
    // MATLAB Elementleri
    const tYuzde = document.getElementById('tahminYuzde');
    const tYorum = document.getElementById('tahminYorum');
    
    // Gemini Elementleri
    const gSkor = document.getElementById('geminiSkor');
    const gYorum = document.getElementById('geminiYorum');

    if (!hisse) {
        status.innerText = "Lütfen bir hisse seçin!";
        return;
    }

    status.innerText = "Veriler analiz ediliyor...";
    tYorum.innerText = "Yükleniyor...";
    gYorum.innerText = "Haberler taranıyor...";

    try {
        // 1. ÖNCE: Python'a hisse verisini indir ve Excel'e (Share_data.xlsx) kaydetmesini söyle
        const resBorsa = await fetch(`${API_BASE}/borsa/${hisse}/${period}`);
        const dataBorsa = await resBorsa.json();

        // Eğer borsa verisi çekilemediyse işlemi durdur
        if (dataBorsa.error) {
            status.innerText = "Hata: " + dataBorsa.error; // Hata mesajını göster
            return;
        }

        // Grafik çizimini başlat
        baslik.innerText = `${dataBorsa.symbol} Analizi`;
        priceDiv.innerText = dataBorsa.current_price.toFixed(2) + " ₺";
        status.innerText = "Güncel";
        ciz(dataBorsa.dates, dataBorsa.prices, dataBorsa.symbol, period);

        // 2. SONRA: Excel başarıyla kaydedildiğine göre MATLAB ve Gemini'yi aynı anda başlat
        const matlabIstek = fetch(`${API_BASE}/tahmin_matlab`);
        const geminiIstek = fetch(`${API_BASE}/analiz_gemini/${hisse}`);

        const [resMatlab, resGemini] = await Promise.all([matlabIstek, geminiIstek]);
        
        const dataMatlab = await resMatlab.json();
        const dataGemini = await resGemini.json();

        // 3. MATLAB Teknik Tahmin İşleme
        if (dataMatlab.hata) {
             tYuzde.innerText = "-";
             tYorum.innerText = "Veri Yok: " + dataMatlab.hata;
        } else {
             const yukselis = (dataMatlab.yukselis_ihtimali * 100).toFixed(1);
             tYuzde.innerText = `%${yukselis}`;
             if (dataMatlab.tahmin === 1) {
                 tYuzde.style.color = "#4ade80"; 
                 tYorum.innerText = "Yükseliş Formasyonu";
             } else {
                 tYuzde.style.color = "#f87171"; 
                 tYorum.innerText = "Düşüş Formasyonu";
             }
        }

        // 4. Gemini Sentiment İşleme
        if (dataGemini.kullanici_raporu) {
             const skor = dataGemini.sayisal_skor;
             let duyguText = "Nötr";
             let renk = "#94a3b8";
             
             if (skor > 0.3) { duyguText = "Pozitif"; renk = "#4ade80"; }
             else if (skor < -0.3) { duyguText = "Negatif"; renk = "#f87171"; }
             
             gSkor.innerText = duyguText;
             gSkor.style.color = renk;
             gYorum.innerText = dataGemini.kullanici_raporu;
        }

    } catch (err) {
        status.innerText = "Bağlantı veya Analiz Hatası!";
        console.error(err);
    }
}

function ciz(labels, prices, symbol, period) {
    const ctx = document.getElementById('borsaGrafik').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: `${symbol} Fiyat`,
                data: prices,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: period === "1gun" ? 0 : 2 
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                x: { 
                    grid: { display: false }, 
                    ticks: { 
                        color: '#94a3b8',
                        maxTicksLimit: period === "1gun" ? 6 : 10,
                        autoSkip: true 
                    } 
                }
            }
        }
    });
}