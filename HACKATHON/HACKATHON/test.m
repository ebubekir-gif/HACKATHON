clear all, clc;

try
    % 1. Python'dan gelen tertemiz dosyayı oku
    Share = readtable("Share_data.xlsx");
    Share = sortrows(Share,"Date","ascend");

    Share.DailyRange = Share.Close - Share.Open;
    Share.PriceRange = Share.High - Share.Low;

    data_size = height(Share);
    
    if data_size < 50
        error('Analiz için yeterli veri yok (En az 50 gün gerekli).');
    end

    % --- RSI HESAPLAMA ---
    avg = diff(Share.Close);
    rsi_values = NaN(data_size,1);
    rsi_period = 14;
    Gains = [0; max(avg, 0)];
    Share.Gain = Gains;
    Losses = [0; abs(min(avg, 0))];
    Share.Loss = Losses;
    meanGain = sum(Gains(2:rsi_period+1))/rsi_period;
    meanLosses = sum(Losses(2:rsi_period+1))/rsi_period;
    if meanLosses == 0
        rs = 100;
    else
        rs = meanGain/meanLosses;
    end
    rsi_values(rsi_period+1) = 100 - 100 / (1 + rs);
    for rsiIndex = (rsi_period+2):data_size
        meanGain = (meanGain*(rsi_period-1) + Gains(rsiIndex))/rsi_period;
        meanLosses = (meanLosses*(rsi_period-1) + Losses(rsiIndex))/rsi_period;
        if meanLosses == 0
            rs = 100;
        else
            rs = meanGain/meanLosses;
        end
        rsi_values(rsiIndex) = 100 - 100 / (1 + rs);
    end
    Share.RSI = rsi_values;

    % --- SHORT EMA ---
    short_ema_values = NaN(data_size,1);
    shortEMA_period = 12;
    shortEMA_Multiplier = 2 / (shortEMA_period + 1);
    short_ema_values(shortEMA_period) = sum(Share.Close(1:shortEMA_period))/shortEMA_period;
    for shortEmaIndex = shortEMA_period+1:data_size
        short_ema_values(shortEmaIndex) = (Share.Close(shortEmaIndex) - short_ema_values(shortEmaIndex-1)) * shortEMA_Multiplier + short_ema_values(shortEmaIndex-1);
    end
    Share.ShortEMA = short_ema_values;

    % --- LONG EMA ---
    long_ema_values = NaN(data_size,1);
    longEMA_period = 26;
    longEMA_Multiplier = 2 / (longEMA_period + 1);
    long_ema_values(longEMA_period) = sum(Share.Close(1:longEMA_period))/longEMA_period;
    for longEmaIndex = longEMA_period+1:data_size
        long_ema_values(longEmaIndex) = (Share.Close(longEmaIndex) - long_ema_values(longEmaIndex-1)) * longEMA_Multiplier + long_ema_values(longEmaIndex-1);
    end
    Share.LongEMA = long_ema_values;

    % --- MACD ---
    Share.MACD_Line = Share.ShortEMA - Share.LongEMA;
    macd_values = NaN(data_size,1);
    macd_period = 9;
    macd_Multiplier = 2 / (macd_period+1);
    macd_startIndex = 26; 
    macd_values(macd_startIndex+macd_period) = sum(Share.MACD_Line(macd_startIndex:macd_startIndex+macd_period))/macd_period;
    for macdIndex = macd_startIndex+macd_period+1:data_size
        macd_values(macdIndex) = (Share.MACD_Line(macdIndex) - macd_values(macdIndex-1)) * macd_Multiplier + macd_values(macdIndex-1);
    end
    Share.MACD = macd_values;

    % --- GETİRİLER VE SAPMALAR ---
    Share.LogReturn = [NaN; diff(log(Share.Close))];
    Share.Lag1_Return = [NaN; Share.LogReturn(1:end-1)];
    Share.Lag2_Return = [NaN; NaN; Share.LogReturn(1:end-2)];
    Share.Lag3_Return = [NaN; NaN; NaN; Share.LogReturn(1:end-3)];
    Share.Dist_ShortEMA = (Share.Close - Share.ShortEMA) ./ Share.ShortEMA;
    Share.Dist_LongEMA = (Share.Close - Share.LongEMA) ./ Share.LongEMA;

    % --- YAPAY ZEKA HEDEFİ ---
    NextDayReturn = [ (Share.Close(2:end) - Share.Close(1:end-1)) ./ Share.Close(1:end-1) ; NaN ];
    Share.Target = double(NextDayReturn > 0.0);
    Share.Target(isnan(NextDayReturn)) = NaN;

    % --- VERİ BÖLME VE EĞİTİM ---
    last_day_features = Share(end, ["RSI", "MACD", "Volume", "DailyRange", "PriceRange", "Lag1_Return", "Lag2_Return", "Lag3_Return", "Dist_ShortEMA", "Dist_LongEMA"]);
    Share(end,:) = [];
    Share = rmmissing(Share);

    X = Share(:, ["RSI", "MACD", "Volume", "DailyRange", "PriceRange", "Lag1_Return", "Lag2_Return", "Lag3_Return", "Dist_ShortEMA", "Dist_LongEMA"]);
    Y = categorical(Share.Target);

    % Rastgeleliği sabitliyoruz ki algoritma tutarlı kararlar versin
    rng('default');
    model = fitcensemble(X, Y, 'Method', 'Bag', 'NumLearningCycles', 50);
    [predicted_label, prediction_scores] = predict(model, last_day_features);

    % --- BAŞARILI SONUÇ ---
    api_result = struct();
    api_result.tahmin = str2double(string(predicted_label(1)));
    api_result.yukselis_ihtimali = prediction_scores(2);
    api_result.dusus_ihtimali = prediction_scores(1);
    api_result.hata = ""; % Hata yok

catch ME
    % --- HATA DURUMU (Yapay zeka çökerse hatayı JSON'a kaydet) ---
    api_result = struct();
    api_result.hata = ME.message;
end

% SONUCU YAZ VE ÇIK
fid = fopen('tahmin_sonucu.json', 'w');
fprintf(fid, '%s', jsonencode(api_result));
fclose(fid);
exit;