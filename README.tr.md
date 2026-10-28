# VLC Subtitle Translator (VLC Altyazı Çevirmeni)

[English](README.md) · **Türkçe**

VLC'de altyazılı video izlerken dil öğrenmek için küçük bir yardımcı (Windows ve Linux).

- **Kelimenin üzerine gel → çevirisi çıkar.** Kelimenin farklı anlamları da görünebilir, istersen bütün cümleyi de çevirebilirsin.
- **Her dilden her dile:** altyazı dilini (öğrendiğin dil) ve çeviri dilini sen seçersin. Örneğin İngilizce → Türkçe, Almanca → İngilizce, İspanyolca → Fransızca.
- **Kelimeyi renklendir:** 🟢 Biliyorum / 🟡 Öğreniyorum / 🔴 Bilmiyorum. Seçtiğin renk o kelime her geçtiğinde aynı görünür.
- **★ ile favorile.** Favori kelimelerin altı çizili görünür. "Kelimelerim / Favoriler" penceresinden hepsini görebilir, arayabilir, çevirisini düzenleyebilir ve CSV (Excel) olarak dışa aktarabilirsin.
- Kelimenin üzerine gelince video otomatik duraklar, fareyi çekince devam eder (ayarlardan kapatılabilir).
- Arayüz **Türkçe ve İngilizce**. Sistem diline göre açılır, pencerenin üstündeki seçiciden değiştirilebilir.

## Nasıl çalışıyor?

VLC'nin eklenti sistemi video üzerindeki fare hareketini algılayamıyor. Bu yüzden program VLC'nin
yanında çalışıyor: VLC'den o anki zamanı alıyor, altyazı dosyasını kendisi okuyor ve altyazıyı
VLC penceresinin üstünde ayrı bir katman olarak gösteriyor. VLC'nin kendi altyazısı otomatik
kapatılıyor, böylece altyazı iki kere görünmüyor.

## Gereksinimler

**Windows 10 / 11**
- [Python 3.10+](https://www.python.org/downloads/). Kurarken "Add python.exe to PATH" seçeneğini işaretle. Ek paket gerekmez.
- [VLC 3](https://www.videolan.org/vlc/)

**Linux** (X11 masaüstü önerilir)
- Tk ile birlikte Python 3.10+:
  - Debian / Ubuntu: `sudo apt install python3 python3-tk`
  - Fedora: `sudo dnf install python3 python3-tkinter`
  - Arch: `sudo pacman -S python tk`
- VLC 3 (dağıtım paketi, Flatpak ya da Snap)

**İkisi için de**
- İsteğe bağlı: PATH'te [ffmpeg](https://ffmpeg.org/). Sadece videonun **içine gömülü** altyazıları okumak için gerekir.
- Kendi çeviri API anahtarın (aşağıya bak).

## Kurulum

1. Bu depoyu indir (**Code → Download ZIP**) ve bir klasöre çıkar, ya da `git clone` ile al.
2. Programı başlat:
   - Windows: **`start.bat`** dosyasına çift tıkla
   - Linux: **`./start.sh`** çalıştır (ya da `python3 vlc_subtitle_translator.py`)
3. Program ilk açılışta "VLC ayarlarını otomatik yapayım mı?" diye sorar, **Evet** de
   (VLC açıksa önce kapatman istenir). Bu adım VLC'nin web arayüzünü **sadece bu bilgisayardan
   erişilebilecek ve rastgele bir şifreyle korunacak** şekilde açar. Eski VLC ayarların, VLC ayar
   dosyasının yanına `vlcrc.vlc-subtitle-translator.bak` olarak yedeklenir.
4. **Çeviri** sekmesinde dilleri seç ve kendi API anahtarını gir (sonraki bölüm).

## Çeviri servisi ve API anahtarı

Bu proje **hiçbir API anahtarı içermez** ve geliştiricinin sunucusu ya da hesabı üzerinden
çalışmaz. Çeviri isteklerini senin bilgisayarın, **senin anahtarınla**, doğrudan seçtiğin servise
gönderir. Anahtarın sadece senin bilgisayarında, `data/ayarlar.json` dosyasında saklanır.
Bu dosyayı kimseyle paylaşma.

Program sadece üzerine geldiğin kelimeyi (ve "Cümleyi çevir" dediğin cümleyi) çevirir, sonucu da
önbelleğe yazar. Aynı kelime ikinci kez çevrilmez. Bu yüzden ücretsiz kotalar normal kullanımda
fazlasıyla yeter.

### Seçenek 1: DeepL API Free (önerilen)

Ayda 500.000 karakter ücretsiz.

1. <https://www.deepl.com/pro-api> adresinde **DeepL API Free** planına kaydol.
   (Kimlik doğrulama için kart istenebilir; Free planda ücret alınmaz.)
2. Hesabında **API Keys** bölümünden anahtarını kopyala. Free anahtarlar `:fx` ile biter.
3. Programda **Çeviri** sekmesinde **DeepL API**'yi seç, anahtarı yapıştır, **Test et**'e bas.

DeepL'in desteklemediği bir dil çifti seçersen çeviri penceresinde hata görürsün.
O zaman Google Cloud'u kullan.

### Seçenek 2: Google Cloud Translation API

Ayda 500.000 karakter ücretsiz, sonrası ücretli. Daha çok dil destekler.

1. <https://console.cloud.google.com/> adresinde bir proje oluştur. Faturalandırma (billing)
   hesabı bağlaman gerekir.
2. **APIs & Services → Library** bölümünden **Cloud Translation API**'yi etkinleştir.
3. **APIs & Services → Credentials → Create credentials → API key** ile anahtar oluştur.
   Güvenlik için anahtarı **API restrictions** ile sadece *Cloud Translation API*'ye kısıtla.
4. Sürpriz fatura olmasın diye **Billing → Budgets & alerts** bölümünden düşük bir bütçe uyarısı kur.
5. Programda **Google Cloud Translation API**'yi seç, anahtarı yapıştır, **Test et**'e bas.

Güncel ücretleri ve kotaları servislerin kendi sayfalarından kontrol et.

### Anahtarsız mod (sadece denemek için)

Anahtar girmeden denemek istersen **Anahtarsız** seçeneği Google Translate'in herkese açık,
**resmi olmayan** ucunu (olmazsa MyMemory'yi) kullanır. Bu uç belgelenmemiştir. Çok istek
gönderen IP'leri geçici olarak engelleyebilir ve her an çalışmayı bırakabilir. Düzenli kullanım
için kendi anahtarınla DeepL ya da Google Cloud'u seç.

## Kullanım

1. Programı başlat ve açık bırak.
2. VLC'de videoyu normal şekilde aç.
3. Altyazı otomatik bulunur:
   - Videonun yanındaki `.srt / .vtt / .ass` dosyası (ör. `film.srt`, `film.en.srt`, `Subs` klasörü).
     Adında altyazı dilin geçen dosya tercih edilir, çeviri dilindeki dosya atlanır.
   - Bulunamazsa videonun içine gömülü altyazı (mkv/mp4, ffmpeg ile çıkarılır).
   - O da yoksa panelden **"Altyazı dosyası seç…"** ile kendin seç.
4. Kelimelerin üzerine gel ve öğrenmeye başla.

Altyazı, VLC penceresi öndeyken görünür, başka bir pencereye geçince gizlenir. Tam ekranda da
çalışır, VLC'nin alttaki oynatma çubuğuyla çakışmaz. VLC'de altyazı gecikmesini (H / G tuşları)
değiştirirsen program da buna uyar.

## Görünüm

**Görünüm** sekmesinde altyazının görünüşünü canlı önizlemeyle ayarlayabilirsin: yazı tipi, boyut,
kalınlık, yazı rengi, siyah kenarlık, arka plan rengi ve opaklığı, yuvarlak köşeler, alttan uzaklık
ve en fazla genişlik.

## Bilinen sınırlamalar

- Linux'ta altyazı arka planı her zaman opak bir kutudur (Tk, X11'de piksel bazında şeffaflık
  desteklemiyor), bu yüzden opaklık ayarı orada etkisizdir. Wayland'da program XWayland üzerinden
  çalışır; pencerenin üstte kalması masaüstüne bağlıdır.
- Kelimeler boşluklara göre ayrılır. Boşluk kullanmayan dillerde (Çince, Japonca, Tayca)
  satırın tamamı tek kelime gibi davranır.
- Sağdan sola yazılan dillerde (Arapça, İbranice, Farsça) altyazı düzgün görünmeyebilir.
- Kelime listen tek bir listedir. Farklı dillerde aynı yazılan kelimeler aynı kaydı paylaşır.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `vlc_subtitle_translator.py` | Ana program ve kontrol paneli |
| `overlay.py` | VLC üstündeki altyazı katmanı ve kelime çeviri penceresi |
| `translator.py` | Çeviri servisleri (DeepL, Google Cloud, anahtarsız) |
| `languages.py` | Desteklenen diller |
| `i18n.py` | Arayüz dili (Türkçe / İngilizce) |
| `words_window.py` | Kelimelerim / Favoriler penceresi |
| `subtitles.py` | Altyazı okuma ve bulma |
| `storage.py` | Kelimelerin, ayarların ve çeviri önbelleğinin kaydı |
| `theme.py` | Koyu arayüz teması |
| `vlc_client.py` | VLC web arayüzüyle iletişim |
| `vlc_setup.py` | VLC ayar dosyasını düzenleme |
| `osutil.py`, `winutil.py`, `x11util.py` | VLC penceresini takip etme (Windows / Linux) |

Kişisel veriler `data/` klasöründe tutulur ve git'e eklenmez:
`ayarlar.json` (VLC şifresi, API anahtarları), `kelimeler.json` (renkler, favoriler; yedeklemek
istersen bu dosyayı kopyala), `ceviri_onbellek.json`, `cache/`.

## Sorun giderme

- **"VLC bulunamadı"**: VLC açık mı? Açıksa VLC'yi kapat, panelde "VLC'yi otomatik ayarla"ya bas, sonra VLC'yi yeniden aç.
- **"Şifre yanlış"**: "VLC'yi otomatik ayarla" ile şifreyi yeniden yazdır.
- **"Çeviri alınamadı: … anahtarı geçersiz"**: Çeviri sekmesinde anahtarı kontrol et, **Test et**'e bas.
- **Altyazı biraz erken/geç**: VLC'de `H` / `G` tuşlarıyla altyazı gecikmesini ayarla.
- Hatalar `data/hata.log` dosyasına yazılır.

## Lisans

[MIT](LICENSE)
