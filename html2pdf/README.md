# HTML → PDF (gerçek, tek sayfa, küçük boyut)

Bu klasördeki araç, bir HTML dosyasını **gerçek** bir PDF'e çevirir:

- **Seçilebilir metin** ve **tıklanabilir linkler** (resimden/yalancı PDF değil).
- **Tek sayfa** — çıktı, içeriğin tam boyutunda tek bir sayfadır; sayfa bölünmesi yoktur.
- **Tarayıcıdaki görünüm** — senin Chrome'unda gördüğün haliyle basılır.
- **Küçük dosya** — gömülü görseller ekrandaki gösterim boyutunun ~3 katına indirilir, fotoğraflar JPEG'e çevrilir. CV'lerde 20+ MB yerine ~2–3 MB.

Bu CV'lerin (sol yeşil kenar çubuklu, `.page` div'li tasarım) ikisi de bununla üretildi.

---

## Kullanım

### En kolay: sürükle-bırak
`HTML to PDF.bat` dosyasının üzerine bir veya birden fazla `.html` dosyasını sürükleyip bırak.
Her `.html` dosyasının yanında aynı adla `.pdf` oluşur.

### Komut satırı
```bat
python html2pdf.py "cv.html"                 :: cv.pdf oluşur
python html2pdf.py "cv.html" -o "cikti.pdf"  :: belirli çıktı adı
python html2pdf.py "C:\klasor"               :: klasördeki tüm .html dosyaları
python html2pdf.py *.html                     :: glob
```

---

## Gereksinimler

- **Python 3** (PATH'te `python`).
- **Google Chrome** kurulu (yoksa Edge'e düşer; o da yoksa Playwright'ın kendi Chromium'unu kullanır).
- İlk çalıştırmada şu paketler otomatik kurulur: `playwright`, `pymupdf`, `pillow`.
  (Ayrı tarayıcı **indirmez** — senin kurulu Chrome'unu kullanır.)

Aracı başka bir makineye taşımak için bu `html2pdf` klasörünü kopyalaman yeterli.

---

## Seçenekler

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `-o, --output` | (girdiyle aynı ad) | Çıktı PDF yolu (yalnız tek girdi için). |
| `--selector` | `.page` | Sayfa boyutunu belirleyen kök eleman. Bu eleman yoksa otomatik `body`. |
| `--media` | `screen` | `screen` = tarayıcı görünümü, `print` = sayfanın `@media print` stili. |
| `--scale` | `3.0` | Görsel kalitesi: gösterim boyutunun kaç katı gömülsün (yüksek = daha net + daha büyük dosya). |
| `--quality` | `92` | Fotoğraf JPEG kalitesi (0–100). |
| `--background` | `#ffffff` | Sayfa zemini (gri gövde çerçevesini kaldırmak için). |
| `--viewport` | `1200` | Render genişliği (px). |
| `--pad` | `3` | Alt boşluk (px). |

Başka bir tasarımda kenar/boyut yanlış çıkarsa kök elemanı belirt:
`python html2pdf.py "sayfa.html" --selector "#cv"`

---

## Nasıl çalışır (teknik özet)

1. **Playwright**, kurulu **Chrome**'u headless başlatır; HTML `file://` ile açılır.
2. Fontlar (`document.fonts.ready`) ve tüm `<img>`'ler yüklenene kadar beklenir.
3. Şu CSS enjekte edilir:
   - `min-height: 0 !important` — **önemli**: orijinal `.page { min-height: 297mm }`, Chrome'un tek-uzun-sayfa baskı yolunda içeriği ilk sayfadan sonra **kırpıyor**. Bunu sıfırlamak tüm içeriği getirir.
   - `margin: 0`, gövde zemini beyaz — sayfayı gri çerçeveden ayırıp PDF'i tam `.page` boyutuna oturtmak için.
4. Kök elemanın boyutu ve **tüm `a[href]` linklerinin** piksel konumları ölçülür.
5. **İki geçiş** ile boyutlama: önce çok uzun tek sayfaya basılır (hiçbir şey bölünmez/kırpılmaz), sonra PyMuPDF ile gerçek içerik yüksekliği ölçülüp tam o yükseklikte yeniden basılır → sıkı tek sayfa.
6. **Görsel küçültme** (PyMuPDF + Pillow): her gömülü görsel, sayfadaki gösterim boyutunun ~3 katına indirilir; saydam olmayanlar JPEG yapılır. (Örn. 3120×4160 fotoğraf 112×150 px gösteriliyordu → ~14 MB'tan ~0,2 MB'a.)
7. **Link enjeksiyonu** (PyMuPDF): Chrome uzun sayfalarda link açıklamalarını yarıda bırakıyor; bu yüzden ölçülen konumlardan **tüm** linkler PDF'e tek tek eklenir. Böylece hepsi tıklanabilir ve doğru yerde olur.

---

## Bir yapay zekâya yaptırman gerekirse

Buna gerek yok — yukarıdaki araç AI'sız, tek komutla çalışıyor. Yine de tarif şu:

> Chrome'u headless çalıştır (Playwright/Puppeteer), HTML'i ekran stiliyle aç, fontları+görselleri bekle, `.page`'e `min-height:0` ver, içeriği **tek bir uzun sayfaya** bas (A4'e bölme), gerçek içerik yüksekliğini ölçüp tam o boyda yeniden bas, gömülü görselleri gösterim boyutunun ~3 katına indir (fotoğrafları JPEG yap), ve tüm `a[href]` linklerini DOM'daki piksel konumlarından PDF'e açıklama (annotation) olarak ekle. Çıktı: tek sayfa, seçilebilir metin, tıklanabilir link, ~2–3 MB.
